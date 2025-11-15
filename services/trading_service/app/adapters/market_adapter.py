from __future__ import annotations

import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from app.core.exchange_client import ExchangeClient
from app.messaging.message_bus import MessageBus
from app.messaging.messages import MarketTickEvent


class MarketDataAdapter:
    """市场数据适配器 - 将交易所数据转换为消息总线事件"""

    def __init__(
        self,
        exchange: ExchangeClient,
        message_bus: MessageBus,
        symbols: List[str],
        poll_interval: float = 1.0
    ):
        self.exchange = exchange
        self.message_bus = message_bus
        self.symbols = symbols
        self.poll_interval = poll_interval
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """启动市场数据适配器"""
        if self._running:
            self.logger.warning("市场数据适配器已在运行")
            return
        
        self._running = True
        self.logger.info(f"市场数据适配器启动 | 监控交易对: {self.symbols}")
        
        # 为每个交易对创建轮询任务
        for symbol in self.symbols:
            task = asyncio.create_task(self._poll_symbol(symbol))
            self._tasks.append(task)

    async def stop(self) -> None:
        """停止市场数据适配器"""
        if not self._running:
            return
        
        self.logger.info("市场数据适配器停止中...")
        self._running = False
        
        # 取消所有任务
        for task in self._tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        self.logger.info("市场数据适配器已停止")

    async def _poll_symbol(self, symbol: str) -> None:
        """轮询单个交易对的市场数据"""
        self.logger.info(f"开始轮询 {symbol}")
        
        while self._running:
            try:
                # 获取ticker数据
                ticker = await self.exchange.fetch_ticker(symbol)
                
                if ticker and 'last' in ticker:
                    # 创建市场tick事件
                    tick_event = MarketTickEvent(
                        symbol=symbol,
                        price=float(ticker['last']),
                        volume=float(ticker.get('baseVolume', 0)),
                        bid=float(ticker.get('bid')) if ticker.get('bid') else None,
                        ask=float(ticker.get('ask')) if ticker.get('ask') else None,
                        timestamp=datetime.utcnow(),
                        metadata={
                            'high': ticker.get('high'),
                            'low': ticker.get('low'),
                            'open': ticker.get('open'),
                            'close': ticker.get('close'),
                            'change': ticker.get('change'),
                            'percentage': ticker.get('percentage')
                        }
                    )
                    
                    # 发布到消息总线
                    await self.message_bus.publish(
                        "market.tick",
                        tick_event.model_dump()
                    )
                    
                    self.logger.debug(
                        f"发布市场tick | {symbol} | 价格: {tick_event.price}"
                    )
                
                # 等待下一次轮询
                await asyncio.sleep(self.poll_interval)
                
            except asyncio.CancelledError:
                self.logger.info(f"轮询任务已取消: {symbol}")
                break
            except Exception as e:
                self.logger.error(
                    f"轮询 {symbol} 失败: {e}",
                    exc_info=True
                )
                # 出错后等待一段时间再重试
                await asyncio.sleep(self.poll_interval * 2)

    def add_symbol(self, symbol: str) -> None:
        """动态添加监控的交易对"""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            if self._running:
                task = asyncio.create_task(self._poll_symbol(symbol))
                self._tasks.append(task)
                self.logger.info(f"已添加监控交易对: {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        """动态移除监控的交易对"""
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            self.logger.info(f"已移除监控交易对: {symbol}")
            # 注意: 对应的任务会在下次循环时自动停止