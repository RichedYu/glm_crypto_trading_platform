"""
适配器模块

提供各种数据源到消息总线的适配器
"""

from app.adapters.market_adapter import MarketDataAdapter

__all__ = [
    "MarketDataAdapter",
]