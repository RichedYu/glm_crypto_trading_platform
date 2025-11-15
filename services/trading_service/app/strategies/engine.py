from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Type, Any
from datetime import datetime

from app.strategies.base import BaseStrategy, StrategyContext, StrategyCapability
from app.messaging.message_bus import MessageBus
from app.messaging.messages import (
    MarketTickEvent,
    StrategySignalEvent,
    StrategyIntentEvent,
    ExecutionCommandEvent,
    OrderFillEvent,
    PositionUpdateEvent,
    OrderCommand,
    VolatilitySurfaceEvent,
    VolatilityForecastEvent,
    PortfolioRiskEvent,
    MacroStateEvent,
)
from app.state.base import StateStore
from app.risk.risk_service import RiskService


class StrategyEngine:
    """策略引擎 - 管理和调度多个策略插件"""

    OPTION_ACTIONS = {"buy_straddle", "sell_straddle", "buy_strangle", "sell_strangle"}

    def __init__(
        self,
        message_bus: MessageBus,
        state_store: StateStore,
        exchange_client: Optional[Any] = None,
        risk_service: Optional[RiskService] = None
    ):
        self.message_bus = message_bus
        self.state_store = state_store
        self.exchange_client = exchange_client
        self.risk_service = risk_service
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 策略注册表
        self._strategies: Dict[str, BaseStrategy] = {}
        self._strategy_classes: Dict[str, Type[BaseStrategy]] = {}
        
        # 运行状态
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # 策略上下文
        self._context = StrategyContext(
            state_store=state_store,
            message_bus=message_bus,
            exchange_client=exchange_client
        )

    def register_strategy_class(
        self,
        strategy_name: str,
        strategy_class: Type[BaseStrategy]
    ) -> None:
        """
        注册策略类
        
        Args:
            strategy_name: 策略名称
            strategy_class: 策略类
        """
        self._strategy_classes[strategy_name] = strategy_class
        self.logger.info(f"已注册策略类: {strategy_name}")

    async def load_strategy(
        self,
        strategy_id: str,
        strategy_name: str,
        config: Dict[str, Any]
    ) -> None:
        """
        加载并初始化策略实例
        
        Args:
            strategy_id: 策略实例ID
            strategy_name: 策略名称
            config: 策略配置
        """
        if strategy_name not in self._strategy_classes:
            raise ValueError(f"未注册的策略类: {strategy_name}")
        
        if strategy_id in self._strategies:
            self.logger.warning(f"策略 {strategy_id} 已存在,将被替换")
            await self.unload_strategy(strategy_id)
        
        # 创建策略实例
        strategy_class = self._strategy_classes[strategy_name]
        strategy = strategy_class(strategy_id, config)
        strategy.set_context(self._context)
        
        # 初始化策略
        await strategy.initialize()
        
        # 注册到引擎
        self._strategies[strategy_id] = strategy
        
        capability = strategy.get_capability()
        self.logger.info(
            f"已加载策略: {strategy_id} ({strategy_name}) | "
            f"交易对: {capability.symbols} | "
            f"工具类型: {[t.value for t in capability.instrument_types]}"
        )

    async def unload_strategy(self, strategy_id: str) -> None:
        """
        卸载策略
        
        Args:
            strategy_id: 策略实例ID
        """
        if strategy_id not in self._strategies:
            self.logger.warning(f"策略 {strategy_id} 不存在")
            return
        
        strategy = self._strategies[strategy_id]
        await strategy.shutdown()
        del self._strategies[strategy_id]
        self.logger.info(f"已卸载策略: {strategy_id}")

    async def start(self) -> None:
        """启动策略引擎"""
        if self._running:
            self.logger.warning("策略引擎已在运行")
            return
        
        self._running = True
        self.logger.info("策略引擎启动中...")
        
        # 启动事件消费任务
        self._tasks.append(
            asyncio.create_task(self._consume_market_ticks())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_order_fills())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_position_updates())
        )
        # 策略信号暂时保持,意图管线新增串行步骤
        self._tasks.append(
            asyncio.create_task(self._consume_strategy_intents())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_volatility_surfaces())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_volatility_forecasts())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_portfolio_risk())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_macro_state())
        )
        
        self.logger.info(f"策略引擎已启动 | 活跃策略数: {len(self._strategies)}")

    async def stop(self) -> None:
        """停止策略引擎"""
        if not self._running:
            return
        
        self.logger.info("策略引擎停止中...")
        self._running = False
        
        # 取消所有任务
        for task in self._tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        # 关闭所有策略
        for strategy_id in list(self._strategies.keys()):
            await self.unload_strategy(strategy_id)
        
        self.logger.info("策略引擎已停止")

    async def _consume_market_ticks(self) -> None:
        """消费市场tick事件"""
        try:
            async for message in self.message_bus.subscribe("market.tick"):
                if not self._running:
                    break
                
                try:
                    tick = MarketTickEvent(**message)
                    await self._dispatch_tick(tick)
                except Exception as e:
                    self.logger.error(f"处理市场tick失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("市场tick消费任务已取消")
        except Exception as e:
            self.logger.error(f"市场tick消费任务异常: {e}", exc_info=True)

    async def _consume_order_fills(self) -> None:
        """消费订单成交事件"""
        try:
            async for message in self.message_bus.subscribe("order.fill"):
                if not self._running:
                    break
                
                try:
                    fill = OrderFillEvent(**message)
                    await self._dispatch_fill(fill)
                except Exception as e:
                    self.logger.error(f"处理订单成交失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("订单成交消费任务已取消")
        except Exception as e:
            self.logger.error(f"订单成交消费任务异常: {e}", exc_info=True)

    async def _consume_position_updates(self) -> None:
        """消费持仓更新事件"""
        try:
            async for message in self.message_bus.subscribe("position.update"):
                if not self._running:
                    break
                
                try:
                    position = PositionUpdateEvent(**message)
                    await self._dispatch_position_update(position)
                except Exception as e:
                    self.logger.error(f"处理持仓更新失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("持仓更新消费任务已取消")
        except Exception as e:
            self.logger.error(f"持仓更新消费任务异常: {e}", exc_info=True)

    async def _consume_strategy_intents(self) -> None:
        """消费策略意图事件,串行执行风控再交给执行层"""
        try:
            async for message in self.message_bus.subscribe("strategy.intent"):
                if not self._running:
                    break

                try:
                    intent = StrategyIntentEvent(**message)
                    await self._process_intent(intent)
                except Exception as e:
                    self.logger.error(f"处理策略意图失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("策略意图消费任务已取消")
        except Exception as e:
            self.logger.error(f"策略意图消费任务异常: {e}", exc_info=True)

    async def _consume_volatility_surfaces(self) -> None:
        """消费波动率曲面事件并分发给策略"""
        try:
            async for message in self.message_bus.subscribe("market.vol_surface"):
                if not self._running:
                    break

                try:
                    vol_surface = VolatilitySurfaceEvent(**message)
                    await self._dispatch_volatility_surface(vol_surface)
                except Exception as e:
                    self.logger.error(f"处理波动率曲面失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("波动率曲面消费任务已取消")
        except Exception as e:
            self.logger.error(f"波动率曲面消费任务异常: {e}", exc_info=True)

    async def _consume_volatility_forecasts(self) -> None:
        """消费波动率预测事件并分发"""
        try:
            async for message in self.message_bus.subscribe("strategy.forecast.volatility"):
                if not self._running:
                    break

                try:
                    forecast = VolatilityForecastEvent(**message)
                    await self._dispatch_volatility_forecast(forecast)
                except Exception as e:
                    self.logger.error(f"处理波动率预测失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("波动率预测消费任务已取消")
        except Exception as e:
            self.logger.error(f"波动率预测消费任务异常: {e}", exc_info=True)

    async def _consume_portfolio_risk(self) -> None:
        """消费 portfolio.risk 流,驱动像 DeltaHedger 这样的策略"""
        try:
            async for message in self.message_bus.subscribe("portfolio.risk"):
                if not self._running:
                    break

                try:
                    risk_event = PortfolioRiskEvent(**message)
                    await self._dispatch_portfolio_risk(risk_event)
                except Exception as e:
                    self.logger.error(f"处理组合风险事件失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("组合风险消费任务已取消")
        except Exception as e:
            self.logger.error(f"组合风险消费任务异常: {e}", exc_info=True)

    async def _consume_macro_state(self) -> None:
        """消费宏观/情绪状态流"""
        try:
            async for message in self.message_bus.subscribe("market.macro_state"):
                if not self._running:
                    break

                try:
                    macro_event = MacroStateEvent(**message)
                    await self._dispatch_macro_state(macro_event)
                except Exception as e:
                    self.logger.error(f"处理宏观状态失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("宏观状态消费任务已取消")
        except Exception as e:
            self.logger.error(f"宏观状态消费任务异常: {e}", exc_info=True)

    async def _process_intent(self, intent: StrategyIntentEvent) -> None:
        """处理策略意图→风控→执行指令"""
        if intent.direction is None:
            self.logger.debug(
                "忽略无方向意图 | %s | %s",
                intent.strategy_id,
                intent.intent_type,
            )
            return

        # 风控检查
        if self.risk_service:
            quantity = intent.quantity or 0.1
            reference_price = intent.metadata.get("reference_price", 0.0)
            risk_check = await self.risk_service.check_pre_order(
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                side=intent.direction,
                quantity=quantity,
                price=reference_price,
            )
            if not risk_check.approved:
                self.logger.warning(
                    "意图被风控拒绝 | %s | action=%s | reason=%s",
                    intent.strategy_id,
                    intent.action,
                    risk_check.reason,
                )
                return

        if intent.action in self.OPTION_ACTIONS:
            execution_event = ExecutionCommandEvent(
                intent_id=intent.intent_id,
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                action=intent.action,
                direction=intent.direction,
                quantity=intent.quantity,
                approved_by="risk_service" if self.risk_service else "engine",
                metadata=intent.metadata,
            )

            await self.message_bus.publish(
                "execution.command",
                execution_event.model_dump(),
            )

            self.logger.info(
                "意图通过风控 -> 发布期权执行命令 | %s | action=%s",
                intent.strategy_id,
                intent.action,
            )
        else:
            order_command = OrderCommand(
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                side=intent.direction,
                order_type="market",
                quantity=intent.quantity,
                price=intent.metadata.get("reference_price"),
                command="create",
                metadata={**intent.metadata, "intent_id": intent.intent_id},
            )

            await self.message_bus.publish("order.command", order_command.model_dump())
            self.logger.info(
                "意图通过风控 -> 直接下单 | %s | action=%s",
                intent.strategy_id,
                intent.action,
            )

    async def _dispatch_tick(self, tick: MarketTickEvent) -> None:
        """分发tick事件到相关策略"""
        for strategy_id, strategy in self._strategies.items():
            try:
                capability = strategy.get_capability()
                # 检查策略是否关注此交易对
                if tick.symbol in capability.symbols:
                    result = await strategy.on_tick(tick)
                    await self._handle_strategy_output(result)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理tick失败: {e}",
                    exc_info=True
                )

    async def _dispatch_fill(self, fill: OrderFillEvent) -> None:
        """分发成交事件到相关策略"""
        strategy_id = fill.strategy_id
        if strategy_id in self._strategies:
            try:
                await self._strategies[strategy_id].on_fill(fill)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理成交失败: {e}",
                    exc_info=True
                )

    async def _dispatch_position_update(self, position: PositionUpdateEvent) -> None:
        """分发持仓更新到相关策略"""
        strategy_id = position.strategy_id
        if strategy_id in self._strategies:
            try:
                await self._strategies[strategy_id].on_position_update(position)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理持仓更新失败: {e}",
                    exc_info=True
                )

    async def _dispatch_portfolio_risk(self, event: PortfolioRiskEvent) -> None:
        for strategy_id, strategy in self._strategies.items():
            handler = getattr(strategy, "on_portfolio_risk", None)
            if not handler:
                continue

            try:
                result = await handler(event)
                await self._handle_strategy_output(result)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理组合风险事件失败: {e}",
                    exc_info=True,
                )

    async def _dispatch_macro_state(self, event: MacroStateEvent) -> None:
        for strategy_id, strategy in self._strategies.items():
            handler = getattr(strategy, "on_macro_state", None)
            if not handler:
                continue

            try:
                result = await handler(event)
                await self._handle_strategy_output(result)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理宏观状态失败: {e}",
                    exc_info=True,
                )

    async def _dispatch_volatility_surface(self, event: VolatilitySurfaceEvent) -> None:
        for strategy_id, strategy in self._strategies.items():
            handler = getattr(strategy, "on_volatility_surface", None)
            if not handler:
                continue

            try:
                result = await handler(event)
                await self._handle_strategy_output(result)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理波动率曲面失败: {e}",
                    exc_info=True,
                )

    async def _dispatch_volatility_forecast(self, event: VolatilityForecastEvent) -> None:
        for strategy_id, strategy in self._strategies.items():
            handler = getattr(strategy, "on_volatility_forecast", None)
            if not handler:
                continue

            try:
                result = await handler(event)
                await self._handle_strategy_output(result)
            except Exception as e:
                self.logger.error(
                    f"策略 {strategy_id} 处理波动率预测失败: {e}",
                    exc_info=True,
                )

    async def _handle_strategy_output(self, result: Optional[Any]) -> None:
        if result is None:
            return

        if isinstance(result, StrategySignalEvent):
            await self._process_legacy_signal(result)
        elif isinstance(result, StrategyIntentEvent):
            await self.message_bus.publish("strategy.intent", result.model_dump())
            self.logger.info(
                f"策略 {result.strategy_id} 生成意图: {result.intent_type}"
            )

    async def _process_legacy_signal(self, signal: StrategySignalEvent) -> None:
        """兼容旧版策略直接输出的 StrategySignalEvent"""
        if signal.signal_type not in ["buy", "sell"]:
            return

        quantity = signal.metadata.get("quantity") or 0.1
        price = signal.target_price or 0.0

        if self.risk_service:
            risk_check = await self.risk_service.check_pre_order(
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                side=signal.signal_type,
                quantity=quantity,
                price=price,
            )
            if not risk_check.approved:
                self.logger.warning(
                    "Legacy信号被风控拒绝 | %s | reason=%s",
                    signal.strategy_id,
                    risk_check.reason,
                )
                return

        order_command = OrderCommand(
            strategy_id=signal.strategy_id,
            symbol=signal.symbol,
            side=signal.signal_type,
            order_type="limit",
            quantity=quantity,
            price=price,
            command="create",
            metadata=signal.metadata,
        )

        await self.message_bus.publish("order.command", order_command.model_dump())
        self.logger.info(
            "Legacy信号 -> 订单命令 | %s | %s %s",
            signal.strategy_id,
            signal.signal_type,
            signal.symbol,
        )

    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """获取活跃策略列表"""
        result = []
        for strategy_id, strategy in self._strategies.items():
            capability = strategy.get_capability()
            result.append({
                "strategy_id": strategy_id,
                "strategy_name": capability.strategy_name,
                "symbols": capability.symbols,
                "instrument_types": [t.value for t in capability.instrument_types],
                "initialized": strategy.is_initialized
            })
        return result
