"""
消息总线模块

提供事件驱动的消息传递基础设施
"""

from app.messaging.message_bus import MessageBus, BusFactory
from app.messaging.redis_bus import RedisStreamBus
from app.messaging.messages import (
    MarketTickEvent,
    StrategySignalEvent,
    OrderCommand,
    OrderFillEvent,
    RiskAlertEvent,
    StateSnapshotEvent,
    PositionUpdateEvent
)

__all__ = [
    "MessageBus",
    "BusFactory",
    "RedisStreamBus",
    "MarketTickEvent",
    "StrategySignalEvent",
    "OrderCommand",
    "OrderFillEvent",
    "RiskAlertEvent",
    "StateSnapshotEvent",
    "PositionUpdateEvent",
]