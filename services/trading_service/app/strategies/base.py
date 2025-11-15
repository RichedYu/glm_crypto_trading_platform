from __future__ import annotations

import abc
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

from app.messaging.messages import (
    MarketTickEvent,
    StrategySignalEvent,
    StrategyIntentEvent,
    OrderFillEvent,
    PositionUpdateEvent,
)


class InstrumentType(Enum):
    """交易工具类型"""
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"
    OPTION = "option"


@dataclass
class StrategyCapability:
    """策略能力元数据"""
    strategy_id: str
    strategy_name: str
    instrument_types: List[InstrumentType]
    symbols: List[str]
    leverage_required: bool = False
    max_leverage: float = 1.0
    min_capital: float = 0.0
    dependencies: List[str] = None  # 依赖的其他服务或数据源

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BaseStrategy(abc.ABC):
    """策略插件基类"""

    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.config = config
        self._initialized = False
        self._context: Optional[StrategyContext] = None

    def set_context(self, context: StrategyContext) -> None:
        """注入运行上下文,便于策略直接访问消息总线/状态等"""
        self._context = context

    @property
    def context(self) -> Optional[StrategyContext]:
        return self._context

    @abc.abstractmethod
    async def initialize(self) -> None:
        """初始化策略"""
        raise NotImplementedError

    @abc.abstractmethod
    async def on_tick(self, tick: MarketTickEvent) -> Optional[StrategySignalEvent]:
        """
        处理市场tick事件
        
        Args:
            tick: 市场行情tick
            
        Returns:
            可选的策略信号
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def on_fill(self, fill: OrderFillEvent) -> None:
        """
        处理订单成交事件
        
        Args:
            fill: 订单成交信息
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def on_position_update(self, position: PositionUpdateEvent) -> None:
        """
        处理持仓更新事件
        
        Args:
            position: 持仓更新信息
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_capability(self) -> StrategyCapability:
        """
        获取策略能力元数据
        
        Returns:
            策略能力描述
        """
        raise NotImplementedError

    async def shutdown(self) -> None:
        """关闭策略,清理资源"""
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """策略是否已初始化"""
        return self._initialized


class StrategyContext:
    """策略上下文,提供策略运行所需的环境"""

    def __init__(
        self,
        state_store: Any,  # StateStore
        message_bus: Any,  # MessageBus
        exchange_client: Any = None
    ):
        self.state_store = state_store
        self.message_bus = message_bus
        self.exchange_client = exchange_client

    async def get_position(self, strategy_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """获取持仓"""
        return await self.state_store.get_position(strategy_id, symbol)

    async def get_balance(self, strategy_id: str) -> Dict[str, float]:
        """获取余额"""
        return await self.state_store.get_balance(strategy_id)

    async def publish_signal(self, signal: StrategySignalEvent) -> None:
        """发布策略信号"""
        await self.message_bus.publish(
            "strategy.signal",
            signal.model_dump()
        )

    async def publish_intent(self, intent: "StrategyIntentEvent") -> None:
        """发布策略意图事件"""
        await self.message_bus.publish(
            "strategy.intent",
            intent.model_dump()
        )

    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取市场数据(如果有exchange_client)"""
        if self.exchange_client:
            ticker = await self.exchange_client.fetch_ticker(symbol)
            return ticker
        return None
