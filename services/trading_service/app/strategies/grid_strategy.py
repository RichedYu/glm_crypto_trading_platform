from __future__ import annotations

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.strategies.base import (
    BaseStrategy,
    StrategyCapability,
    InstrumentType
)
from app.messaging.messages import (
    MarketTickEvent,
    StrategySignalEvent,
    OrderFillEvent,
    PositionUpdateEvent
)


class GridStrategy(BaseStrategy):
    """网格交易策略插件"""

    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.logger = logging.getLogger(f"{self.__class__.__name__}[{strategy_id}]")
        
        # 策略参数
        self.symbol = config.get("symbol", "BNB/USDT")
        self.base_price = config.get("base_price", 0.0)
        self.grid_size = config.get("grid_size", 2.0)
        self.flip_threshold_factor = config.get("flip_threshold_factor", 0.3)
        
        # 状态变量
        self.current_price: Optional[float] = None
        self.highest: Optional[float] = None
        self.lowest: Optional[float] = None
        self.last_trade_time: Optional[float] = None
        self.last_trade_price: Optional[float] = None
        self.buying_or_selling = False
        
        # 最小交易间隔(秒)
        self.min_trade_interval = config.get("min_trade_interval", 30)

    async def initialize(self) -> None:
        """初始化策略"""
        self.logger.info(
            f"初始化网格策略 | 交易对: {self.symbol} | "
            f"基准价: {self.base_price} | 网格: {self.grid_size}%"
        )
        self._initialized = True

    def get_capability(self) -> StrategyCapability:
        """获取策略能力"""
        return StrategyCapability(
            strategy_id=self.strategy_id,
            strategy_name="GridStrategy",
            instrument_types=[InstrumentType.SPOT],
            symbols=[self.symbol],
            leverage_required=False,
            max_leverage=1.0,
            min_capital=100.0,
            dependencies=[]
        )

    async def on_tick(self, tick: MarketTickEvent) -> Optional[StrategySignalEvent]:
        """处理市场tick"""
        if tick.symbol != self.symbol:
            return None
        
        self.current_price = tick.price
        
        # 检查交易间隔
        if self.last_trade_time:
            elapsed = time.time() - self.last_trade_time
            if elapsed < self.min_trade_interval:
                return None
        
        # 检查卖出信号
        sell_signal = await self._check_sell_signal()
        if sell_signal:
            return sell_signal
        
        # 检查买入信号
        buy_signal = await self._check_buy_signal()
        if buy_signal:
            return buy_signal
        
        return None

    async def on_fill(self, fill: OrderFillEvent) -> None:
        """处理订单成交"""
        self.logger.info(
            f"订单成交 | {fill.side} | "
            f"价格: {fill.price} | 数量: {fill.quantity}"
        )
        
        # 更新基准价
        self.base_price = fill.price
        self.last_trade_price = fill.price
        self.last_trade_time = time.time()
        
        # 重置极值
        self._reset_extremes()

    async def on_position_update(self, position: PositionUpdateEvent) -> None:
        """处理持仓更新"""
        self.logger.debug(
            f"持仓更新 | {position.symbol} | "
            f"数量: {position.quantity} | 均价: {position.avg_price}"
        )

    async def _check_buy_signal(self) -> Optional[StrategySignalEvent]:
        """检查买入信号"""
        if not self.current_price:
            return None
        
        lower_band = self._get_lower_band()
        
        if self.current_price <= lower_band:
            self.buying_or_selling = True
            
            # 更新最低价
            new_lowest = (
                self.current_price 
                if self.lowest is None 
                else min(self.lowest, self.current_price)
            )
            
            if new_lowest != self.lowest:
                self.lowest = new_lowest
                self.logger.info(
                    f"买入监测 | 当前价: {self.current_price:.2f} | "
                    f"触发价: {lower_band:.2f} | 最低价: {self.lowest:.2f}"
                )
            
            # 检查反弹
            threshold = self._get_flip_threshold()
            if self.lowest and self.current_price >= self.lowest * (1 + threshold):
                self.buying_or_selling = False
                self.logger.info(
                    f"触发买入信号 | 当前价: {self.current_price:.2f} | "
                    f"已从最低价 {self.lowest:.2f} 反弹"
                )
                
                return StrategySignalEvent(
                    strategy_id=self.strategy_id,
                    signal_type="buy",
                    symbol=self.symbol,
                    confidence=1.0,
                    target_price=self.current_price,
                    metadata={
                        "grid_size": self.grid_size,
                        "base_price": self.base_price,
                        "lowest_price": self.lowest
                    }
                )
        else:
            if self.buying_or_selling:
                self._reset_extremes()
                self.buying_or_selling = False
        
        return None

    async def _check_sell_signal(self) -> Optional[StrategySignalEvent]:
        """检查卖出信号"""
        if not self.current_price:
            return None
        
        upper_band = self._get_upper_band()
        
        if self.current_price >= upper_band:
            self.buying_or_selling = True
            
            # 更新最高价
            new_highest = (
                self.current_price 
                if self.highest is None 
                else max(self.highest, self.current_price)
            )
            
            if new_highest != self.highest:
                self.highest = new_highest
                self.logger.info(
                    f"卖出监测 | 当前价: {self.current_price:.2f} | "
                    f"触发价: {upper_band:.2f} | 最高价: {self.highest:.2f}"
                )
            
            # 检查回调
            threshold = self._get_flip_threshold()
            if self.highest and self.current_price <= self.highest * (1 - threshold):
                self.buying_or_selling = False
                self.logger.info(
                    f"触发卖出信号 | 当前价: {self.current_price:.2f} | "
                    f"已从最高价 {self.highest:.2f} 回调"
                )
                
                return StrategySignalEvent(
                    strategy_id=self.strategy_id,
                    signal_type="sell",
                    symbol=self.symbol,
                    confidence=1.0,
                    target_price=self.current_price,
                    metadata={
                        "grid_size": self.grid_size,
                        "base_price": self.base_price,
                        "highest_price": self.highest
                    }
                )
        else:
            if self.buying_or_selling:
                self._reset_extremes()
                self.buying_or_selling = False
        
        return None

    def _get_upper_band(self) -> float:
        """获取上轨"""
        return self.base_price * (1 + self.grid_size / 100)

    def _get_lower_band(self) -> float:
        """获取下轨"""
        return self.base_price * (1 - self.grid_size / 100)

    def _get_flip_threshold(self) -> float:
        """获取反转阈值"""
        return (self.grid_size / 100) * self.flip_threshold_factor

    def _reset_extremes(self) -> None:
        """重置极值"""
        if self.highest is not None or self.lowest is not None:
            self.logger.debug(
                f"重置极值 | highest={self.highest} lowest={self.lowest}"
            )
        self.highest = None
        self.lowest = None