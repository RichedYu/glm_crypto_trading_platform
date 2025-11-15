from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import aiohttp

from app.messaging.message_bus import MessageBus
from app.messaging.messages import (
    OrderFillEvent,
    RiskAlertEvent,
    PortfolioRiskEvent,
    MacroStateEvent,
)
from app.state.portfolio_store import PortfolioStateStore
from app.core.exchange_client import ExchangeClient
from app.adapters.options_adapter import BlackScholesCalculator


class RiskCheckResult:
    """风控检查结果"""
    
    def __init__(self, approved: bool, reason: str = "", metrics: Optional[Dict[str, Any]] = None):
        self.approved = approved
        self.reason = reason
        self.metrics = metrics or {}


class RiskService:
    """
    风险管理服务
    
    职责:
    1. 订阅order.fill事件,实时更新全局投资组合状态
    2. 提供Pre-Order Veto检查
    3. 监控风险指标并发送告警
    """

    def __init__(
        self,
        message_bus: MessageBus,
        portfolio_store: PortfolioStateStore,
        exchange: Optional[ExchangeClient] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.message_bus = message_bus
        self.portfolio_store = portfolio_store
        self.exchange = exchange
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 风控配置
        self.config = config or {}
        self.max_drawdown_pct = self.config.get("max_drawdown_pct", 0.20)  # 最大回撤20%
        self.max_position_ratio = self.config.get("max_position_ratio", 0.80)  # 最大仓位80%
        self.min_position_ratio = self.config.get("min_position_ratio", 0.10)  # 最小底仓10%
        self.max_single_position_pct = self.config.get("max_single_position_pct", 0.30)  # 单个持仓最大30%
        self.macro_broadcast_interval = self.config.get("macro_broadcast_interval", 60)
        self.sentiment_api_urls = self.config.get("sentiment_api_urls", [
            "http://sentiment_service:8000",
            "http://localhost:8002",
        ])

        # 运行状态
        self._running = False
        self._tasks = []
        
        # 初始资产价值(用于计算回撤)
        self._initial_value: Optional[float] = None
        self._peak_value: Optional[float] = None

    async def start(self) -> None:
        """启动风险服务"""
        if self._running:
            self.logger.warning("风险服务已在运行")
            return
        
        self._running = True
        self.logger.info("风险服务启动中...")
        
        # 初始化峰值
        self._peak_value = await self.portfolio_store.get_peak_value()
        if self._peak_value == 0:
            # 首次启动,获取当前资产作为初始值
            current_value = await self._calculate_total_value()
            self._initial_value = current_value
            self._peak_value = current_value
            self.logger.info(f"初始化资产价值: {current_value:.2f}")
        
        # 启动事件消费任务
        self._tasks.append(
            asyncio.create_task(self._consume_order_fills())
        )
        self._tasks.append(
            asyncio.create_task(self._periodic_risk_check())
        )
        self._tasks.append(
            asyncio.create_task(self._macro_state_broadcast_loop())
        )
        
        self.logger.info("风险服务已启动")

    async def stop(self) -> None:
        """停止风险服务"""
        if not self._running:
            return
        
        self.logger.info("风险服务停止中...")
        self._running = False
        
        # 取消所有任务
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        self.logger.info("风险服务已停止")

    async def _consume_order_fills(self) -> None:
        """消费订单成交事件"""
        try:
            async for message in self.message_bus.subscribe("order.fill"):
                if not self._running:
                    break
                
                try:
                    fill = OrderFillEvent(**message)
                    await self._process_fill(fill)
                except Exception as e:
                    self.logger.error(f"处理订单成交失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("订单成交消费任务已取消")
        except Exception as e:
            self.logger.error(f"订单成交消费任务异常: {e}", exc_info=True)

    async def _process_fill(self, fill: OrderFillEvent) -> None:
        """处理订单成交,更新全局状态"""
        self.logger.info(
            f"处理成交 | {fill.symbol} | {fill.side} | "
            f"数量: {fill.quantity} | 价格: {fill.price}"
        )
        
        # 获取当前持仓
        current_position = await self.portfolio_store.get_position(fill.symbol)
        
        if current_position:
            current_qty = current_position["quantity"]
            current_avg = current_position["avg_price"]
        else:
            current_qty = 0.0
            current_avg = 0.0
        
        # 计算新持仓
        if fill.side == "buy":
            new_qty = current_qty + fill.quantity
            if new_qty > 0:
                new_avg = (current_qty * current_avg + fill.quantity * fill.price) / new_qty
            else:
                new_avg = fill.price
        else:  # sell
            new_qty = current_qty - fill.quantity
            new_avg = current_avg  # 卖出不改变平均价
        
        # 更新持仓
        await self.portfolio_store.update_position(
            symbol=fill.symbol,
            quantity=new_qty,
            avg_price=new_avg,
            unrealized_pnl=0.0,  # 稍后计算
            strategy_id=fill.strategy_id
        )
        
        # 更新余额(如果有exchange)
        if self.exchange:
            try:
                balance = await self.exchange.fetch_balance()
                balances = {
                    "USDT": float(balance.get("free", {}).get("USDT", 0)),
                    "BNB": float(balance.get("free", {}).get("BNB", 0))
                }
                await self.portfolio_store.update_global_balance(balances)
            except Exception as e:
                self.logger.error(f"更新余额失败: {e}")
        
        # 计算并记录PnL
        await self._update_pnl()
        
        # 更新风险指标
        await self._update_risk_metrics()

    async def _periodic_risk_check(self) -> None:
        """定期风险检查"""
        try:
            while self._running:
                await asyncio.sleep(60)  # 每分钟检查一次
                
                try:
                    # 检查回撤
                    drawdown_check = await self._check_drawdown()
                    if not drawdown_check.approved:
                        await self._send_risk_alert(
                            "drawdown",
                            "critical",
                            drawdown_check.reason,
                            drawdown_check.metrics
                        )
                    
                    # 检查仓位
                    position_check = await self._check_position_limits()
                    if not position_check.approved:
                        await self._send_risk_alert(
                            "position_limit",
                            "warning",
                            position_check.reason,
                            position_check.metrics
                        )
                    
                except Exception as e:
                    self.logger.error(f"定期风险检查失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("定期风险检查任务已取消")

    async def check_pre_order(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> RiskCheckResult:
        """
        Pre-Order Veto检查
        
        在发送订单前必须通过此检查
        
        Args:
            strategy_id: 策略ID
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            price: 价格
            
        Returns:
            RiskCheckResult: 检查结果
        """
        self.logger.info(
            f"Pre-Order检查 | 策略: {strategy_id} | "
            f"{symbol} {side} {quantity} @ {price}"
        )
        
        # 1. 检查回撤
        drawdown_check = await self._check_drawdown()
        if not drawdown_check.approved:
            return drawdown_check
        
        # 2. 检查仓位限制
        position_check = await self._check_position_limits()
        if not position_check.approved:
            return position_check
        
        # 3. 模拟订单后的仓位
        simulated_check = await self._simulate_order_impact(
            symbol, side, quantity, price
        )
        if not simulated_check.approved:
            return simulated_check
        
        self.logger.info("Pre-Order检查通过")
        return RiskCheckResult(approved=True, reason="所有风控检查通过")

    async def _check_drawdown(self) -> RiskCheckResult:
        """检查回撤"""
        current_value = await self._calculate_total_value()
        
        if self._peak_value is None or current_value > self._peak_value:
            self._peak_value = current_value
            await self.portfolio_store.record_drawdown(
                current_value=current_value,
                peak_value=self._peak_value,
                drawdown_pct=0.0
            )
            return RiskCheckResult(approved=True)
        
        drawdown_pct = (self._peak_value - current_value) / self._peak_value
        
        await self.portfolio_store.record_drawdown(
            current_value=current_value,
            peak_value=self._peak_value,
            drawdown_pct=drawdown_pct
        )
        
        if drawdown_pct > self.max_drawdown_pct:
            return RiskCheckResult(
                approved=False,
                reason=f"回撤超限: {drawdown_pct:.2%} > {self.max_drawdown_pct:.2%}",
                metrics={
                    "current_value": current_value,
                    "peak_value": self._peak_value,
                    "drawdown_pct": drawdown_pct
                }
            )
        
        return RiskCheckResult(approved=True)

    async def _check_position_limits(self) -> RiskCheckResult:
        """检查仓位限制"""
        total_value = await self._calculate_total_value()
        if total_value == 0:
            return RiskCheckResult(approved=True)
        
        positions = await self.portfolio_store.get_all_positions()
        balances = await self.portfolio_store.get_global_balance()
        
        # 计算总仓位价值
        position_value = 0.0
        for symbol, pos in positions.items():
            position_value += pos["quantity"] * pos["avg_price"]
        
        position_ratio = position_value / total_value
        
        # 检查最大仓位
        if position_ratio > self.max_position_ratio:
            return RiskCheckResult(
                approved=False,
                reason=f"仓位超限: {position_ratio:.2%} > {self.max_position_ratio:.2%}",
                metrics={"position_ratio": position_ratio}
            )
        
        # 检查最小底仓
        if position_ratio < self.min_position_ratio:
            return RiskCheckResult(
                approved=False,
                reason=f"底仓不足: {position_ratio:.2%} < {self.min_position_ratio:.2%}",
                metrics={"position_ratio": position_ratio}
            )
        
        return RiskCheckResult(approved=True)

    async def _simulate_order_impact(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> RiskCheckResult:
        """
        模拟订单对仓位和杠杆的影响

        目标:
        - 控制单个标的的集中度 (max_single_position_pct)
        - 控制组合总杠杆(名义敞口/净资产)
        - 为 Web3 场景下现货/期权/合约统一风险视角做准备
        """
        # 获取当前持仓
        current_position = await self.portfolio_store.get_position(symbol)
        current_qty = current_position["quantity"] if current_position else 0.0

        # 计算新仓位数量
        if side == "buy":
            new_qty = current_qty + quantity
        else:
            new_qty = current_qty - quantity

        # 计算组合总价值
        total_value = await self._calculate_total_value()
        if total_value == 0:
            # 没有资产时不做杠杆限制,交给上层资金管理
            return RiskCheckResult(approved=True)

        # --- 1) 单个标的集中度检查 (与原逻辑保持一致,稍作扩展) ---
        new_position_value = new_qty * price
        position_pct = new_position_value / total_value

        if position_pct > self.max_single_position_pct:
            return RiskCheckResult(
                approved=False,
                reason=(
                    f"单个持仓超限: {position_pct:.2%} "
                    f"> {self.max_single_position_pct:.2%}"
                ),
                metrics={
                    "position_pct": position_pct,
                    "symbol": symbol,
                    "total_value": total_value,
                    "new_position_value": new_position_value,
                },
            )

        # --- 2) 组合杠杆检查 (gross leverage) ---
        # 计算当前组合的总名义敞口(绝对值)
        positions = await self.portfolio_store.get_all_positions()
        current_gross_notional = 0.0
        for sym, pos in positions.items():
            qty = pos.get("quantity", 0.0)
            avg = pos.get("avg_price", 0.0)
            current_gross_notional += abs(qty * avg)

        # 当前订单的名义敞口(现货/合约近似: qty * price)
        order_notional = abs(quantity * price)
        new_gross_notional = current_gross_notional + order_notional
        new_leverage = new_gross_notional / total_value if total_value > 0 else 0.0

        # 允许通过 config 自定义最大杠杆,否则使用一个相对保守的默认值
        max_leverage = self.config.get("max_gross_leverage", 3.0)

        if new_leverage > max_leverage:
            return RiskCheckResult(
                approved=False,
                reason=(
                    f"组合杠杆超限: {new_leverage:.2f}x > {max_leverage:.2f}x"
                ),
                metrics={
                    "new_leverage": new_leverage,
                    "max_leverage": max_leverage,
                    "current_gross_notional": current_gross_notional,
                    "new_gross_notional": new_gross_notional,
                    "order_notional": order_notional,
                    "total_value": total_value,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                },
            )

        return RiskCheckResult(
            approved=True,
            reason="单个持仓和组合杠杆均在安全范围内",
            metrics={
                "position_pct": position_pct,
                "new_leverage": new_leverage,
            },
        )

    async def _calculate_total_value(self) -> float:
        """计算总资产价值"""
        balances = await self.portfolio_store.get_global_balance()
        positions = await self.portfolio_store.get_all_positions()
        
        total = balances.get("USDT", 0.0)
        
        # 加上持仓价值(简化计算,使用平均价)
        for symbol, pos in positions.items():
            total += pos["quantity"] * pos["avg_price"]
        
        return total

    async def _update_pnl(self) -> None:
        """更新PnL"""
        # 简化实现,实际应该计算已实现和未实现盈亏
        total_value = await self._calculate_total_value()
        
        await self.portfolio_store.record_pnl(
            realized_pnl=0.0,  # TODO: 计算已实现盈亏
            unrealized_pnl=0.0,  # TODO: 计算未实现盈亏
            total_value=total_value
        )

    async def _update_risk_metrics(self) -> None:
        """更新风险指标,包括Greeks计算"""
        total_value = await self._calculate_total_value()
        positions = await self.portfolio_store.get_all_positions()
        
        position_value = 0.0
        total_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0
        total_rho = 0.0
        
        # 计算每个持仓的Greeks并汇总
        for symbol, pos in positions.items():
            pos_value = pos["quantity"] * pos["avg_price"]
            position_value += pos_value
            
            # 如果是期权持仓,计算Greeks
            if "-C" in symbol or "-P" in symbol:
                greeks = pos.get("greeks", {})
                if greeks:
                    # Greeks已存在,直接使用
                    total_delta += greeks.get("delta", 0) * pos["quantity"]
                    total_gamma += greeks.get("gamma", 0) * pos["quantity"]
                    total_vega += greeks.get("vega", 0) * pos["quantity"]
                    total_theta += greeks.get("theta", 0) * pos["quantity"]
                    total_rho += greeks.get("rho", 0) * pos["quantity"]
                else:
                    # Greeks不存在,尝试计算
                    calculated_greeks = await self._calculate_position_greeks(symbol, pos)
                    if calculated_greeks:
                        total_delta += calculated_greeks.delta * pos["quantity"]
                        total_gamma += calculated_greeks.gamma * pos["quantity"]
                        total_vega += calculated_greeks.vega * pos["quantity"]
                        total_theta += calculated_greeks.theta * pos["quantity"]
                        total_rho += calculated_greeks.rho * pos["quantity"]
            else:
                # 现货/期货持仓,Delta = 数量
                total_delta += pos["quantity"]
        
        position_ratio = position_value / total_value if total_value > 0 else 0
        
        metrics = {
            "total_value": total_value,
            "position_value": position_value,
            "position_ratio": position_ratio,
            "num_positions": len(positions),
            "total_delta": total_delta,
            "total_gamma": total_gamma,
            "total_vega": total_vega,
            "total_theta": total_theta,
            "total_rho": total_rho
        }
        
        await self.portfolio_store.update_risk_metrics(metrics)

        self.logger.debug(
            f"风险指标更新 | Delta: {total_delta:.4f} | "
            f"Gamma: {total_gamma:.4f} | Vega: {total_vega:.4f}"
        )

        # 广播组合风险事件,供DeltaHedger等实时消费
        if self.message_bus:
            event = PortfolioRiskEvent(
                total_delta=total_delta,
                total_gamma=total_gamma,
                total_vega=total_vega,
                total_theta=total_theta,
                total_rho=total_rho,
                position_ratio=position_ratio,
                leverage=metrics.get("leverage"),
                metadata={
                    "total_value": total_value,
                    "position_value": position_value,
                },
            )
            await self.message_bus.publish("portfolio.risk", event.model_dump())

    async def _macro_state_broadcast_loop(self) -> None:
        """周期性推送宏观/情绪状态到消息总线"""
        if not self.message_bus:
            return

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while self._running:
                try:
                    sentiment = await self._fetch_sentiment_score(session)
                    realized_vol = await self._estimate_realized_vol()
                    macro_regime, regime_score = self._infer_macro_state(realized_vol, sentiment)
                    fomo_score = self._compute_fomo_score(sentiment, realized_vol)

                    event = MacroStateEvent(
                        macro_regime=macro_regime,
                        regime_score=regime_score,
                        sentiment_score=sentiment,
                        fomo_score=fomo_score,
                    )
                    await self.message_bus.publish("market.macro_state", event.model_dump())
                except Exception as e:
                    self.logger.warning(f"广播宏观状态失败: {e}")

                await asyncio.sleep(self.macro_broadcast_interval)

    async def _fetch_sentiment_score(self, session: aiohttp.ClientSession) -> Optional[float]:
        for base_url in self.sentiment_api_urls:
            try:
                async with session.get(
                    f"{base_url}/api/v1/sentiment/twitter",
                    params={"query": "BTC", "max_results": 20},
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    score = data.get("weighted_score")
                    if score is not None:
                        return float(score)
            except Exception as exc:
                self.logger.debug(f"获取情绪数据失败({base_url}): {exc}")
        return None

    async def _estimate_realized_vol(self) -> Optional[float]:
        try:
            pnl_points = await self.portfolio_store.get_recent_pnl(limit=2)
            if len(pnl_points) < 2:
                return None
            prev = pnl_points[-2]["total_value"] or 1.0
            curr = pnl_points[-1]["total_value"] or prev
            change = abs(curr - prev) / max(abs(prev), 1.0)
            return float(min(1.5, change))
        except Exception as exc:
            self.logger.debug(f"估算实现波动率失败: {exc}")
            return None

    def _infer_macro_state(self, realized_vol: Optional[float], sentiment: Optional[float]) -> tuple[str, float]:
        vol = realized_vol if realized_vol is not None else 0.4
        sent = sentiment if sentiment is not None else 0.0

        high_vol = vol > 0.8
        mid_vol = 0.4 < vol <= 0.8
        low_vol = vol <= 0.4

        very_bullish = sent > 0.7
        bullish = 0.3 < sent <= 0.7
        neutral = -0.3 <= sent <= 0.3
        bearish = -0.7 <= sent < -0.3
        very_bearish = sent < -0.7

        if high_vol and very_bearish:
            return "panic", min(1.0, (vol - 0.8) + abs(sent))
        if high_vol and very_bullish:
            return "high_vol_bull", min(1.0, (vol - 0.8) + sent)
        if (low_vol or mid_vol) and bullish:
            return "bull", min(1.0, 0.5 * vol + sent)
        if (mid_vol or high_vol) and bearish:
            return "bear", min(1.0, vol + abs(sent))
        if low_vol and neutral:
            return "chop", min(1.0, 0.2 + vol)
        return "unknown", 0.1

    def _compute_fomo_score(self, sentiment: Optional[float], realized_vol: Optional[float]) -> Optional[float]:
        if sentiment is None or realized_vol is None:
            return None
        return float(max(0.0, min(1.0, 0.6 * sentiment + 0.4 * realized_vol)))
    
    async def _calculate_position_greeks(
        self,
        symbol: str,
        position: Dict[str, Any]
    ) -> Optional[Any]:
        """
        计算持仓的Greeks
        
        Args:
            symbol: 合约符号(如BTC-20241229-40000-C)
            position: 持仓信息
            
        Returns:
            OptionGreeks对象或None
        """
        try:
            # 解析期权合约符号
            parts = symbol.split("-")
            if len(parts) != 4:
                return None
            
            underlying, expiry, strike_str, option_type = parts
            strike = float(strike_str)
            option_type = "call" if option_type == "C" else "put"
            
            # 获取标的现价
            if self.exchange:
                ticker = await self.exchange.fetch_ticker(f"{underlying}/USDT")
                spot_price = float(ticker.get("last", 0))
            else:
                spot_price = position["avg_price"]  # 回退方案
            
            # 计算到期时间
            expiry_date = datetime.strptime(expiry, "%Y%m%d")
            time_to_expiry = max((expiry_date - datetime.utcnow()).days / 365.0, 0.001)
            
            # 假设波动率和无风险利率
            volatility = 0.6  # TODO: 从市场数据获取
            risk_free_rate = 0.03
            
            # 计算Greeks
            bs_calc = BlackScholesCalculator()
            greeks = bs_calc.calculate_greeks(
                spot_price, strike, time_to_expiry,
                risk_free_rate, volatility, option_type
            )
            
            # 保存Greeks到持仓
            await self.portfolio_store.update_position_greeks(
                symbol,
                {
                    "delta": greeks.delta,
                    "gamma": greeks.gamma,
                    "theta": greeks.theta,
                    "vega": greeks.vega,
                    "rho": greeks.rho
                }
            )
            
            return greeks
            
        except Exception as e:
            self.logger.error(f"计算Greeks失败 | {symbol} | {e}")
            return None

    async def _send_risk_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metrics: Dict[str, Any]
    ) -> None:
        """发送风险告警"""
        alert = RiskAlertEvent(
            strategy_id="global",
            alert_type=alert_type,
            severity=severity,
            message=message,
            current_value=metrics.get("current_value", 0.0),
            threshold_value=metrics.get("threshold_value", 0.0),
            metadata=metrics
        )
        
        await self.message_bus.publish("risk.alert", alert.model_dump())
        self.logger.warning(f"风险告警 | {severity} | {message}")
