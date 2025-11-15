from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np
from scipy.stats import norm

from app.core.exchange_client import ExchangeClient
from app.messaging.message_bus import MessageBus
from app.messaging.messages import (
    OptionChainData,
    OptionGreeks,
    VolatilitySurfaceEvent
)


class BlackScholesCalculator:
    """Black-Scholes期权定价和Greeks计算"""
    
    @staticmethod
    def calculate_iv(
        option_price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        option_type: str
    ) -> float:
        """
        使用牛顿法反算隐含波动率
        
        Args:
            option_price: 期权市场价格
            spot: 标的现价
            strike: 行权价
            time_to_expiry: 到期时间(年)
            risk_free_rate: 无风险利率
            option_type: "call" 或 "put"
            
        Returns:
            隐含波动率
        """
        if time_to_expiry <= 0 or option_price <= 0:
            return 0.0
        
        # 初始猜测
        sigma = 0.5
        max_iterations = 100
        tolerance = 1e-5
        
        for _ in range(max_iterations):
            price = BlackScholesCalculator._bs_price(
                spot, strike, time_to_expiry, risk_free_rate, sigma, option_type
            )
            vega = BlackScholesCalculator._bs_vega(
                spot, strike, time_to_expiry, risk_free_rate, sigma
            )
            
            diff = option_price - price
            
            if abs(diff) < tolerance:
                return sigma
            
            if vega < 1e-10:
                break
            
            sigma = sigma + diff / vega
            
            # 确保sigma在合理范围内
            sigma = max(0.01, min(sigma, 5.0))
        
        return sigma
    
    @staticmethod
    def calculate_greeks(
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: str
    ) -> OptionGreeks:
        """计算期权Greeks"""
        if time_to_expiry <= 0:
            return OptionGreeks(delta=0, gamma=0, theta=0, vega=0, rho=0)
        
        d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        if option_type == "call":
            delta = norm.cdf(d1)
            rho = strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
        else:  # put
            delta = -norm.cdf(-d1)
            rho = -strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
        
        gamma = norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_expiry))
        vega = spot * norm.pdf(d1) * np.sqrt(time_to_expiry) / 100
        theta = (-spot * norm.pdf(d1) * volatility / (2 * np.sqrt(time_to_expiry)) 
                 - risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2 if option_type == "call" else -d2)) / 365
        
        return OptionGreeks(
            delta=float(delta),
            gamma=float(gamma),
            theta=float(theta),
            vega=float(vega),
            rho=float(rho)
        )
    
    @staticmethod
    def _bs_price(spot, strike, time, rate, vol, option_type):
        """Black-Scholes价格"""
        d1 = (np.log(spot / strike) + (rate + 0.5 * vol ** 2) * time) / (vol * np.sqrt(time))
        d2 = d1 - vol * np.sqrt(time)
        
        if option_type == "call":
            return spot * norm.cdf(d1) - strike * np.exp(-rate * time) * norm.cdf(d2)
        else:
            return strike * np.exp(-rate * time) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    
    @staticmethod
    def _bs_vega(spot, strike, time, rate, vol):
        """Black-Scholes Vega"""
        d1 = (np.log(spot / strike) + (rate + 0.5 * vol ** 2) * time) / (vol * np.sqrt(time))
        return spot * norm.pdf(d1) * np.sqrt(time)


class OptionsChainAdapter:
    """
    期权链数据适配器 - P-World (市场在想什么)
    
    职责:
    1. 拉取期权合约市场价格
    2. 反算隐含波动率(IV)
    3. 计算Greeks
    4. 构建波动率曲面
    5. 发布到消息总线
    """

    def __init__(
        self,
        exchange: ExchangeClient,
        message_bus: MessageBus,
        underlying: str = "BTC/USDT",
        poll_interval: float = 60.0,  # 期权数据更新较慢,60秒一次
        risk_free_rate: float = 0.03  # 无风险利率3%
    ):
        self.exchange = exchange
        self.message_bus = message_bus
        self.underlying = underlying
        self.poll_interval = poll_interval
        self.risk_free_rate = risk_free_rate
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.bs_calc = BlackScholesCalculator()

    async def start(self) -> None:
        """启动期权链适配器"""
        if self._running:
            self.logger.warning("期权链适配器已在运行")
            return
        
        self._running = True
        self.logger.info(f"期权链适配器启动 | 标的: {self.underlying}")
        
        self._task = asyncio.create_task(self._poll_options_chain())

    async def stop(self) -> None:
        """停止期权链适配器"""
        if not self._running:
            return
        
        self.logger.info("期权链适配器停止中...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("期权链适配器已停止")

    async def _poll_options_chain(self) -> None:
        """轮询期权链数据"""
        while self._running:
            try:
                # 获取标的现价
                spot_price = await self._get_spot_price()
                if not spot_price:
                    await asyncio.sleep(self.poll_interval)
                    continue
                
                # 获取期权链数据
                options_data = await self._fetch_options_chain(spot_price)
                
                if options_data:
                    # 构建波动率曲面
                    vol_surface = await self._build_volatility_surface(
                        options_data, spot_price
                    )
                    
                    # 发布到消息总线
                    await self.message_bus.publish(
                        "market.vol_surface",
                        vol_surface.model_dump()
                    )
                    
                    self.logger.info(
                        f"发布波动率曲面 | {self.underlying} | "
                        f"ATM IV: {vol_surface.atm_iv:.2%} | "
                        f"合约数: {len(vol_surface.surface_data)}"
                    )
                
                await asyncio.sleep(self.poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"轮询期权链失败: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval * 2)

    async def _get_spot_price(self) -> Optional[float]:
        """获取标的现价"""
        try:
            ticker = await self.exchange.fetch_ticker(self.underlying)
            return float(ticker.get("last", 0))
        except Exception as e:
            self.logger.error(f"获取现价失败: {e}")
            return None

    async def _fetch_options_chain(self, spot_price: float) -> List[OptionChainData]:
        """
        获取期权链数据
        
        注意: 这是简化实现,实际需要调用交易所期权API
        """
        options_data = []
        
        try:
            # TODO: 实际实现需要调用交易所期权API
            # 这里使用模拟数据作为示例
            
            # 生成不同行权价的期权
            strikes = [
                spot_price * 0.9,  # 10% OTM put
                spot_price * 0.95,  # 5% OTM put
                spot_price,  # ATM
                spot_price * 1.05,  # 5% OTM call
                spot_price * 1.10   # 10% OTM call
            ]
            
            expiries = ["2024-12-29", "2025-01-31", "2025-03-31"]  # 不同到期日
            
            for expiry in expiries:
                time_to_expiry = self._calculate_time_to_expiry(expiry)
                
                for strike in strikes:
                    for option_type in ["call", "put"]:
                        # 模拟期权价格(实际应从交易所获取)
                        option_price = self._simulate_option_price(
                            spot_price, strike, time_to_expiry, option_type
                        )
                        
                        # 反算隐含波动率
                        iv = self.bs_calc.calculate_iv(
                            option_price, spot_price, strike,
                            time_to_expiry, self.risk_free_rate, option_type
                        )
                        
                        # 计算Greeks
                        greeks = self.bs_calc.calculate_greeks(
                            spot_price, strike, time_to_expiry,
                            self.risk_free_rate, iv, option_type
                        )
                        
                        option_data = OptionChainData(
                            underlying=self.underlying,
                            strike=strike,
                            expiry=expiry,
                            option_type=option_type,
                            bid=option_price * 0.99,
                            ask=option_price * 1.01,
                            last=option_price,
                            volume=100.0,
                            open_interest=500.0,
                            implied_volatility=iv,
                            greeks=greeks
                        )
                        
                        options_data.append(option_data)
            
        except Exception as e:
            self.logger.error(f"获取期权链失败: {e}", exc_info=True)
        
        return options_data

    def _simulate_option_price(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        option_type: str
    ) -> float:
        """模拟期权价格(实际应从交易所获取)"""
        # 使用假设的波动率计算理论价格
        assumed_vol = 0.6  # 假设60%波动率
        return self.bs_calc._bs_price(
            spot, strike, time_to_expiry,
            self.risk_free_rate, assumed_vol, option_type
        )

    def _calculate_time_to_expiry(self, expiry_str: str) -> float:
        """计算到期时间(年)"""
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            now = datetime.utcnow()
            days_to_expiry = (expiry_date - now).days
            return max(days_to_expiry / 365.0, 0.001)  # 最小0.001年
        except:
            return 0.25  # 默认3个月

    async def _build_volatility_surface(
        self,
        options_data: List[OptionChainData],
        spot_price: float
    ) -> VolatilitySurfaceEvent:
        """构建波动率曲面"""
        # 计算ATM隐含波动率
        atm_options = [
            opt for opt in options_data
            if abs(opt.strike - spot_price) / spot_price < 0.02  # 2%以内视为ATM
        ]
        
        if atm_options:
            atm_iv = np.mean([opt.implied_volatility for opt in atm_options])
        else:
            atm_iv = 0.5  # 默认50%
        
        # 构建波动率偏斜(按行权价)
        iv_skew = {}
        for opt in options_data:
            key = f"{opt.strike:.0f}"
            if key not in iv_skew:
                iv_skew[key] = opt.implied_volatility
        
        # 构建期限结构(按到期日)
        term_structure = {}
        for opt in options_data:
            if opt.expiry not in term_structure:
                expiry_options = [o for o in options_data if o.expiry == opt.expiry]
                term_structure[opt.expiry] = np.mean([o.implied_volatility for o in expiry_options])
        
        return VolatilitySurfaceEvent(
            underlying=self.underlying,
            surface_data=options_data,
            atm_iv=float(atm_iv),
            iv_skew=iv_skew,
            term_structure=term_structure
        )