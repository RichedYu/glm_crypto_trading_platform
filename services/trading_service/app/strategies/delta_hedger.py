from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from app.strategies.base import (
    BaseStrategy,
    StrategyCapability,
    InstrumentType
)
from app.messaging.messages import (
    MarketTickEvent,
    StrategyIntentEvent,
    OrderFillEvent,
    PositionUpdateEvent,
    PortfolioRiskEvent,
)


class DeltaHedgerStrategy(BaseStrategy):
    """
    Delta对冲策略 - Gamma Scalping的核心
    
    目标: 保持投资组合的总Delta敞口始终为零(或接近零)
    
    工作原理:
    1. 监控全局投资组合的total_delta
    2. 当total_delta偏离目标(通常是0)超过阈值时
    3. 自动发出对冲订单(通常是永续合约或期货)
    4. 使Delta重新归零
    
    这实现了Gamma Scalping:
    - 价格上涨 → Long Gamma使Delta变正 → 卖出期货对冲 → 高位卖出
    - 价格下跌 → Delta变负 → 买入期货对冲 → 低位买入
    - 自动"高卖低买",这就是波动率交易的利润来源
    """

    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.logger = logging.getLogger(f"{self.__class__.__name__}[{strategy_id}]")
        
        # 策略参数
        self.underlying = config.get("underlying", "BTC/USDT")
        self.hedge_instrument = config.get("hedge_instrument", "BTC/USDT:USDT")  # 永续合约
        self.delta_threshold = config.get("delta_threshold", 0.05)  # Delta阈值
        self.hedge_cooldown_seconds = config.get("rebalance_interval", 60)
        
        # 状态变量
        self.current_total_delta: float = 0.0
        self.last_hedge_time: Optional[datetime] = None
        self.hedge_position: float = 0.0  # 当前对冲仓位
        
        self._running = False

    async def initialize(self) -> None:
        """初始化策略"""
        self.logger.info(
            f"初始化Delta对冲策略 | "
            f"标的: {self.underlying} | "
            f"对冲工具: {self.hedge_instrument} | "
            f"Delta阈值: {self.delta_threshold}"
        )
        self._initialized = True
        self._running = True

    def get_capability(self) -> StrategyCapability:
        """获取策略能力"""
        return StrategyCapability(
            strategy_id=self.strategy_id,
            strategy_name="DeltaHedgerStrategy",
            instrument_types=[InstrumentType.PERPETUAL, InstrumentType.FUTURES],
            symbols=[self.hedge_instrument],
            leverage_required=True,
            max_leverage=5.0,
            min_capital=100.0,
            dependencies=["portfolio_store", "risk_service"]
        )

    async def on_tick(self, tick: MarketTickEvent) -> Optional[StrategySignalEvent]:
        """
        处理市场tick
        
        注意: 此策略主要通过轮询portfolio_store工作
        """
        return None

    async def on_portfolio_risk(self, event: PortfolioRiskEvent) -> Optional[StrategyIntentEvent]:
        """组合风险更新时触发,用于实时Delta对冲"""
        return await self._check_hedge_needed(event.total_delta)

    async def _check_hedge_needed(self, total_delta: float) -> Optional[StrategyIntentEvent]:
        """
        检查是否需要对冲
        
        Args:
            total_delta: 当前投资组合总Delta
            
        Returns:
            对冲信号(如果需要)
        """
        self.current_total_delta = total_delta
        
        # 如果Delta在阈值内,不需要对冲
        if abs(total_delta) < self.delta_threshold:
            self.logger.debug(
                f"Delta在阈值内 | "
                f"当前: {total_delta:+.4f} | 阈值: ±{self.delta_threshold}"
            )
            return None
        
        # 检查对冲冷却时间
        if self.last_hedge_time:
            elapsed = (datetime.utcnow() - self.last_hedge_time).total_seconds()
            if elapsed < self.rebalance_interval:
                return None
        
        # 计算需要对冲的数量
        # Delta为正 → 需要卖出(做空)期货
        # Delta为负 → 需要买入(做多)期货
        hedge_quantity = -total_delta  # 反向对冲
        
        self.logger.info(
            f"需要Delta对冲 | "
            f"当前Delta: {total_delta:+.4f} | "
            f"对冲数量: {hedge_quantity:+.4f}"
        )
        
        intent = StrategyIntentEvent(
            intent_id=str(uuid4()),
            strategy_id=self.strategy_id,
            symbol=self.hedge_instrument,
            intent_type="delta_hedge",
            action="delta_hedge",
            direction="buy" if hedge_quantity > 0 else "sell",
            quantity=abs(hedge_quantity),
            confidence=1.0,
            reason="maintain_delta_neutral",
            metadata={
                "strategy_type": "delta_hedger",
                "current_delta": total_delta,
                "hedge_quantity": abs(hedge_quantity),
            }
        )
        
        self.last_hedge_time = datetime.utcnow()
        return intent

    async def on_fill(self, fill: OrderFillEvent) -> None:
        """处理订单成交"""
        self.logger.info(
            f"对冲订单成交 | {fill.side} | "
            f"数量: {fill.quantity} | 价格: {fill.price}"
        )
        
        # 更新对冲仓位
        if fill.side == "buy":
            self.hedge_position += fill.quantity
        else:
            self.hedge_position -= fill.quantity
        
        self.logger.info(f"当前对冲仓位: {self.hedge_position:+.4f}")

    async def on_position_update(self, position: PositionUpdateEvent) -> None:
        """处理持仓更新"""
        if position.symbol == self.hedge_instrument:
            self.hedge_position = position.quantity
            self.logger.debug(
                f"对冲仓位更新 | {position.symbol} | "
                f"数量: {position.quantity:+.4f}"
            )

    async def update_total_delta(self, total_delta: float) -> Optional[StrategyIntentEvent]:
        """
        外部更新total_delta的接口
        
        当RiskService或PortfolioStore检测到Delta变化时调用
        
        Args:
            total_delta: 新的总Delta值
            
        Returns:
            对冲信号(如果需要)
        """
        return await self._check_hedge_needed(total_delta)

    async def shutdown(self) -> None:
        """关闭策略"""
        self._running = False
        await super().shutdown()

    async def get_strategy_state(self) -> Dict[str, Any]:
        """获取策略状态(用于监控)"""
        return {
            "strategy_id": self.strategy_id,
            "underlying": self.underlying,
            "hedge_instrument": self.hedge_instrument,
            "current_total_delta": self.current_total_delta,
            "hedge_position": self.hedge_position,
            "delta_threshold": self.delta_threshold,
            "last_hedge_time": self.last_hedge_time.isoformat() if self.last_hedge_time else None
        }
