from __future__ import annotations

import asyncio
import logging
from typing import Optional, List, Dict, Any

from app.messaging.message_bus import MessageBus
from app.messaging.messages import (
    ExecutionCommandEvent,
    OrderCommand,
    VolatilitySurfaceEvent,
    OptionChainData,
)


class OptionExecutionService:
    """
    期权执行服务 - 策略语言到交易所语言的转换层
    
    职责:
    1. 订阅 execution.command 流(已经过 StrategyEngine 风控)
    2. 识别期权相关动作(如"buy_straddle", "sell_strangle")
    3. 从 market.vol_surface 获取当前期权链
    4. 将意图转换为具体期权合约订单
    5. 发布 order.command 到消息总线
    
    示例:
    - 输入: "买入ATM跨式"
    - 输出: "买入BTC-20241229-40000-C" + "买入BTC-20241229-40000-P"
    """

    def __init__(
        self,
        message_bus: MessageBus
    ):
        self.message_bus = message_bus
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 缓存最新的波动率曲面
        self._vol_surfaces: Dict[str, VolatilitySurfaceEvent] = {}
        
        # 运行状态
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """启动期权执行服务"""
        if self._running:
            self.logger.warning("期权执行服务已在运行")
            return
        
        self._running = True
        self.logger.info("期权执行服务启动中...")
        
        # 启动消费任务
        self._tasks.append(
            asyncio.create_task(self._consume_execution_commands())
        )
        self._tasks.append(
            asyncio.create_task(self._consume_vol_surfaces())
        )
        
        self.logger.info("期权执行服务已启动")

    async def stop(self) -> None:
        """停止期权执行服务"""
        if not self._running:
            return
        
        self.logger.info("期权执行服务停止中...")
        self._running = False
        
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        self.logger.info("期权执行服务已停止")

    async def _consume_execution_commands(self) -> None:
        """消费风控后的执行命令"""
        try:
            async for message in self.message_bus.subscribe("execution.command"):
                if not self._running:
                    break

                try:
                    command = ExecutionCommandEvent(**message)
                    await self._process_execution_command(command)
                except Exception as e:
                    self.logger.error(f"处理执行命令失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("执行命令消费任务已取消")
        except Exception as e:
            self.logger.error(f"执行命令消费任务异常: {e}", exc_info=True)

    async def _consume_vol_surfaces(self) -> None:
        """消费波动率曲面,保持最新数据"""
        try:
            async for message in self.message_bus.subscribe("market.vol_surface"):
                if not self._running:
                    break
                
                try:
                    vol_surface = VolatilitySurfaceEvent(**message)
                    self._vol_surfaces[vol_surface.underlying] = vol_surface
                    self.logger.debug(
                        f"更新波动率曲面缓存 | {vol_surface.underlying}"
                    )
                except Exception as e:
                    self.logger.error(f"处理波动率曲面失败: {e}", exc_info=True)
        except asyncio.CancelledError:
            self.logger.info("波动率曲面消费任务已取消")
        except Exception as e:
            self.logger.error(f"波动率曲面消费任务异常: {e}", exc_info=True)

    async def _process_execution_command(self, command: ExecutionCommandEvent) -> None:
        """把执行命令翻译成具体期权订单"""
        action = command.action
        if not action:
            return

        self.logger.info(
            "处理执行命令 | 策略: %s | 动作: %s | 标的: %s",
            command.strategy_id,
            action,
            command.symbol,
        )

        if action == "buy_straddle":
            await self._execute_straddle(command, "buy")
        elif action == "sell_straddle":
            await self._execute_straddle(command, "sell")
        elif action == "buy_strangle":
            await self._execute_strangle(command, "buy")
        elif action == "sell_strangle":
            await self._execute_strangle(command, "sell")
        else:
            self.logger.debug("未识别的执行动作: %s", action)

    async def _execute_straddle(
        self,
        command: ExecutionCommandEvent,
        side: str
    ) -> None:
        """
        执行跨式策略
        
        跨式 = ATM Call + ATM Put (相同行权价和到期日)
        
        Args:
            signal: 策略信号
            side: "buy" 或 "sell"
        """
        underlying = command.symbol
        
        # 获取波动率曲面
        vol_surface = self._vol_surfaces.get(underlying)
        if not vol_surface:
            self.logger.warning(
                f"未找到波动率曲面 | {underlying} | 无法执行跨式"
            )
            return
        
        # 找到ATM期权
        atm_options = self._find_atm_options(vol_surface)
        
        if not atm_options:
            self.logger.warning(f"未找到ATM期权 | {underlying}")
            return
        
        # 生成Call和Put的订单命令
        for option in atm_options:
            order_command = OrderCommand(
                strategy_id=command.strategy_id,
                symbol=self._format_option_symbol(option),
                side=side,
                order_type="limit",
                quantity=command.quantity or command.metadata.get("quantity", 0.1),
                price=option.last,
                command="create",
                metadata={
                    "intent_id": command.intent_id,
                    "option_type": option.option_type,
                    "strike": option.strike,
                    "expiry": option.expiry,
                    "strategy": "straddle"
                }
            )
            
            # 发布订单命令
            await self.message_bus.publish(
                "order.command",
                order_command.model_dump()
            )
            
            self.logger.info(
                f"发布期权订单 | {side} | "
                f"{option.option_type.upper()} | "
                f"行权价: {option.strike} | "
                f"到期: {option.expiry}"
            )

    async def _execute_strangle(
        self,
        command: ExecutionCommandEvent,
        side: str
    ) -> None:
        """
        执行宽跨式策略
        
        宽跨式 = OTM Call + OTM Put (不同行权价,相同到期日)
        
        Args:
            signal: 策略信号
            side: "buy" 或 "sell"
        """
        # TODO: 实现宽跨式逻辑
        self.logger.info(f"宽跨式策略待实现 | {command.strategy_id}")

    def _find_atm_options(
        self,
        vol_surface: VolatilitySurfaceEvent
    ) -> List[OptionChainData]:
        """
        找到ATM(平值)期权
        
        Args:
            vol_surface: 波动率曲面
            
        Returns:
            ATM的Call和Put期权列表
        """
        if not vol_surface.surface_data:
            return []
        
        # 获取最近到期的期权
        expiries = sorted(set(opt.expiry for opt in vol_surface.surface_data))
        if not expiries:
            return []
        
        nearest_expiry = expiries[0]
        
        # 筛选最近到期的期权
        nearest_options = [
            opt for opt in vol_surface.surface_data
            if opt.expiry == nearest_expiry
        ]
        
        # 找到最接近ATM的行权价
        strikes = sorted(set(opt.strike for opt in nearest_options))
        if not strikes:
            return []
        
        # 假设标的现价在strikes中间
        mid_idx = len(strikes) // 2
        atm_strike = strikes[mid_idx]
        
        # 找到ATM的Call和Put
        atm_options = [
            opt for opt in nearest_options
            if opt.strike == atm_strike
        ]
        
        return atm_options

    def _format_option_symbol(self, option: OptionChainData) -> str:
        """
        格式化期权合约符号
        
        示例: BTC-20241229-40000-C
        
        Args:
            option: 期权数据
            
        Returns:
            格式化的合约符号
        """
        underlying_base = option.underlying.split("/")[0]  # BTC/USDT -> BTC
        expiry_str = option.expiry.replace("-", "")  # 2024-12-29 -> 20241229
        strike_str = f"{int(option.strike)}"
        type_str = "C" if option.option_type == "call" else "P"
        
        return f"{underlying_base}-{expiry_str}-{strike_str}-{type_str}"
