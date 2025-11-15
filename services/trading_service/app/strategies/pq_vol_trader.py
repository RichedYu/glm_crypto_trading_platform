from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass

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
    VolatilitySurfaceEvent,
    VolatilityForecastEvent,
    MacroStateEvent,
)


@dataclass
class MarketState:
    """
    策略内部使用的聚合状态,统一把 P/Q、宏观 Q、情绪/FOMO 和风险信息放在一起,用于意图决策。
    """
    underlying: str

    # 波动率相关
    p_vol: Optional[float]
    q_vol: Optional[float]
    pq_spread: Optional[float]

    # 宏观 regime (由 strategy_service 提供),如果暂时没有接线,可以为 None 或 "unknown"
    macro_regime: Optional[str] = None
    regime_score: float = 0.0

    # 情绪 / FOMO 相关(来自 sentiment_service 或上游注入)
    sentiment_score: Optional[float] = None
    fomo_score: Optional[float] = None

    # 风险/头寸相关(由 RiskService/PortfolioStateStore 提供后可接入)
    total_delta: Optional[float] = None
    total_gamma: Optional[float] = None
    leverage: Optional[float] = None
    drawdown_pct: Optional[float] = None


class PQVolTraderStrategy(BaseStrategy):
    """
    P vs Q 波动率交易策略
    
    策略逻辑:
    - P (市场隐含波动率): 从期权链反算的IV
    - Q (预测波动率): GLM模型预测的未来波动率
    - 当 Q > P + 阈值时,买入跨式(做多波动率)
    - 当 P > Q + 阈值时,卖出跨式(做空波动率)
    
    这是量化交易的核心: 交易市场预期(P)和模型预测(Q)的差价
    """

    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.logger = logging.getLogger(f"{self.__class__.__name__}[{strategy_id}]")
        
        # 策略参数
        self.underlying = config.get("underlying", "BTC/USDT")
        self.vol_threshold = config.get("vol_threshold", 0.05)  # 5%波动率差异阈值
        self.forecast_horizon = config.get("forecast_horizon", "24h")
        self.max_position_size = config.get("max_position_size", 1.0)
        self.intent_base_size = config.get("intent_base_size", 0.1)
        
        # 【新增】FOMO/杀猪盘防御相关参数
        # 当短期涨幅和情绪同时极端时,限制加仓行为
        self.max_intraday_return = config.get("max_intraday_return", 0.15)  # 单日最大追涨容忍度15%
        self.max_fomo_score = config.get("max_fomo_score", 0.7)  # 情绪+涨幅综合FOMO阈值
        # 将来可从 sentiment_service 注入更多特征(如提及量/关键词),这里先预留
        self.latest_fomo_score: Optional[float] = None

        # 【预留】宏观 regime/Q 相关状态(未来从 strategy_service 注入)
        self.macro_regime: Optional[str] = None
        self.regime_score: float = 0.0
        self.latest_sentiment_score: Optional[float] = None

        # 状态变量
        self.latest_p_vol: Optional[float] = None  # 最新市场隐含波动率
        self.latest_q_vol: Optional[float] = None  # 最新预测波动率
        self.last_signal_time: Optional[datetime] = None
        self.current_position: float = 0.0  # 当前持仓(正数=做多波动率,负数=做空)
        
        # 信号冷却时间(避免频繁交易)
        self.signal_cooldown_seconds = config.get("signal_cooldown", 3600)  # 1小时

    async def initialize(self) -> None:
        """初始化策略"""
        self.logger.info(
            f"初始化P vs Q波动率交易策略 | "
            f"标的: {self.underlying} | "
            f"阈值: {self.vol_threshold:.2%}"
        )
        self._initialized = True

    def get_capability(self) -> StrategyCapability:
        """获取策略能力"""
        return StrategyCapability(
            strategy_id=self.strategy_id,
            strategy_name="PQVolTraderStrategy",
            instrument_types=[InstrumentType.OPTION],  # 期权策略
            symbols=[self.underlying],
            leverage_required=False,
            max_leverage=1.0,
            min_capital=1000.0,
            dependencies=["options_chain_adapter", "volatility_forecast_service"]
        )

    async def on_tick(self, tick: MarketTickEvent) -> Optional[StrategyIntentEvent]:
        """
        处理市场tick
        
        注意: 此策略不直接响应tick,而是订阅波动率事件
        """
        return None

    async def on_volatility_surface(
        self,
        vol_surface: VolatilitySurfaceEvent
    ) -> Optional[StrategyIntentEvent]:
        """
        处理波动率曲面事件(P-World)
        
        这个方法需要在策略引擎中被调用
        """
        if vol_surface.underlying != self.underlying:
            return None
        
        # 更新P值(市场隐含波动率)
        self.latest_p_vol = vol_surface.atm_iv
        
        self.logger.debug(
            f"更新P值 | ATM IV: {self.latest_p_vol:.2%}"
        )
        
        # 如果有Q值,检查是否需要交易
        if self.latest_q_vol is not None:
            return await self._check_pq_spread()
        
        return None

    async def on_volatility_forecast(
        self,
        forecast: VolatilityForecastEvent
    ) -> Optional[StrategyIntentEvent]:
        """
        处理波动率预测事件(Q-World)
        
        这个方法需要在策略引擎中被调用
        """
        if forecast.underlying != self.underlying:
            return None
        
        if forecast.forecast_horizon != self.forecast_horizon:
            return None
        
        # 更新Q值(预测波动率)
        self.latest_q_vol = forecast.predicted_volatility
        
        self.logger.debug(
            f"更新Q值 | 预测波动率: {self.latest_q_vol:.2%} | "
            f"置信度: {forecast.confidence:.2%}"
        )
        
        # 如果有P值,检查是否需要交易
        if self.latest_p_vol is not None:
            return await self._check_pq_spread()

        return None

    async def on_macro_state(self, event: MacroStateEvent) -> None:
        """订阅宏观/情绪状态,实时更新策略环境"""
        if event.symbol and event.symbol != self.underlying:
            return

        self.macro_regime = event.macro_regime or self.macro_regime
        self.regime_score = event.regime_score or self.regime_score
        self.latest_sentiment_score = event.sentiment_score or self.latest_sentiment_score
        self.latest_fomo_score = event.fomo_score or self.latest_fomo_score
        
        return None

    def _build_market_state(self) -> Optional[MarketState]:
        """
        聚合当前已知的 P/Q、宏观信息、情绪和风险状态。

        目前宏观/风险部分多数是占位,重点是先把结构搭好,后续可以从:
        - strategy_service 注入 macro_regime/regime_score
        - sentiment_service 注入 sentiment_score/fomo_score
        - RiskService/PortfolioStateStore 注入 total_delta/total_gamma/leverage/drawdown_pct
        """
        if self.latest_p_vol is None or self.latest_q_vol is None:
            return None

        pq_spread = self.latest_q_vol - self.latest_p_vol

        state = MarketState(
            underlying=self.underlying,
            p_vol=self.latest_p_vol,
            q_vol=self.latest_q_vol,
            pq_spread=pq_spread,
            macro_regime=self.macro_regime,
            regime_score=self.regime_score,
            sentiment_score=self.latest_sentiment_score,
            fomo_score=self.latest_fomo_score,
            # 下面这些目前暂时为 None,后续可从 RiskService/state 注入
            total_delta=None,
            total_gamma=None,
            leverage=None,
            drawdown_pct=None,
        )

        return state

    def _decide_intent(self, state: MarketState) -> Optional[Dict[str, Any]]:
        """
        意图决策器: 根据 MarketState 决定当前应该采取的高层动作。

        返回一个简单 dict,包含:
        - intent_type: "increase_long_gamma" / "reduce_long_gamma" / "hold" / ...
        - direction: "buy" / "sell" / None
        - reason/metadata: 附加信息,方便日志与风控/前端查看

        注意: 最新架构下,本方法直接返回 StrategyIntentEvent,
        由策略引擎统一进行风控和执行。
        """
        # 基础 sanity check
        if state.p_vol is None or state.q_vol is None or state.pq_spread is None:
            return None

        pq_spread = state.pq_spread

        self.logger.info(
            "状态评估 | P(市场): %.2f%% | Q(预测): %.2f%% | PQ差: %+0.2f%% | "
            "macro_regime=%s | regime_score=%.2f | fomo_score=%s",
            state.p_vol * 100,
            state.q_vol * 100,
            pq_spread * 100,
            state.macro_regime or "unknown",
            state.regime_score,
            f"{state.fomo_score:.3f}" if state.fomo_score is not None else "None",
        )

        # 1) FOMO/杀猪盘防御: FOMO 过高时不允许扩大仓位,直接 HOLD
        if (
            state.fomo_score is not None
            and self.max_fomo_score is not None
            and state.fomo_score > self.max_fomo_score
        ):
            return {
                "intent_type": "hold",
                "direction": None,
                "reason": "high_fomo_risk",
                "metadata": {"fomo_score": state.fomo_score},
            }

        # 2) 经典 P/Q 逻辑: 决定是偏多 Gamma 还是偏空 Gamma
        # 做多波动率: Q > P + threshold
        if pq_spread > self.vol_threshold and self.current_position < self.max_position_size:
            return {
                "intent_type": "increase_long_gamma",
                "direction": "buy",
                "reason": "market_underpricing_volatility",
                "metadata": {
                    "pq_spread": pq_spread,
                    "macro_regime": state.macro_regime,
                    "regime_score": state.regime_score,
                },
            }

        # 做空波动率: P > Q + threshold
        if pq_spread < -self.vol_threshold and self.current_position > -self.max_position_size:
            return {
                "intent_type": "increase_short_gamma",
                "direction": "sell",
                "reason": "market_overpricing_volatility",
                "metadata": {
                    "pq_spread": pq_spread,
                    "macro_regime": state.macro_regime,
                    "regime_score": state.regime_score,
                },
            }

        # 3) 默认: 不调整
        return {
            "intent_type": "hold",
            "direction": None,
            "reason": "threshold_not_met",
            "metadata": {"pq_spread": pq_spread},
        }

    async def _check_pq_spread(self) -> Optional[StrategyIntentEvent]:
        """
        检查P-Q价差,决定是否交易

        核心逻辑:
        - State 聚合: 先构建 MarketState
        - Intent 决策: 调用 _decide_intent 得到高层意图
        - 输出 StrategyIntentEvent,StrategyEngine 会统一发布 Intent 流
        """
        # 冷却时间检查
        if self.last_signal_time:
            elapsed = (datetime.utcnow() - self.last_signal_time).total_seconds()
            if elapsed < self.signal_cooldown_seconds:
                return None

        # 构建状态
        state = self._build_market_state()
        if not state:
            return None

        # 意图决策
        intent = self._decide_intent(state)
        if not intent or intent.get("direction") is None:
            return None

        direction = intent["direction"]
        metadata = intent.get("metadata", {})
        reason = intent.get("reason", "")

        # 计算本次可用头寸(避免超过最大仓位)
        if direction == "buy":
            available = max(0.0, self.max_position_size - self.current_position)
        else:
            # direction == sell, current_position 可能为正/负
            available = max(0.0, self.max_position_size + self.current_position)

        quantity = min(self.intent_base_size, available)
        if quantity <= 0:
            return None

        intent_event = StrategyIntentEvent(
            intent_id=str(uuid4()),
            strategy_id=self.strategy_id,
            symbol=self.underlying,
            intent_type=intent.get("intent_type", "hold"),
            action="buy_straddle" if direction == "buy" else "sell_straddle",
            direction=direction,
            quantity=quantity,
            confidence=min(abs(state.pq_spread or 0.0) / self.vol_threshold, 1.0),
            reason=reason,
            metadata={
                "strategy_type": "pq_vol_trader",
                "p_vol": state.p_vol,
                "q_vol": state.q_vol,
                "pq_spread": state.pq_spread,
                "fomo_score": state.fomo_score,
                "macro_regime": state.macro_regime,
                "regime_score": state.regime_score,
                "quantity": quantity,
                **metadata,
            },
        )

        self.last_signal_time = datetime.utcnow()
        return intent_event

    async def on_fill(self, fill: OrderFillEvent) -> None:
        """处理订单成交"""
        self.logger.info(
            f"订单成交 | {fill.side} | "
            f"数量: {fill.quantity} | 价格: {fill.price}"
        )
        
        # 更新持仓
        if fill.side == "buy":
            self.current_position += fill.quantity
        else:
            self.current_position -= fill.quantity
        
        self.logger.info(f"当前波动率持仓: {self.current_position:+.2f}")

    async def on_position_update(self, position: PositionUpdateEvent) -> None:
        """处理持仓更新"""
        self.logger.debug(
            f"持仓更新 | {position.symbol} | "
            f"数量: {position.quantity}"
        )
        
        # 同步持仓状态
        self.current_position = position.quantity

    async def get_strategy_state(self) -> Dict[str, Any]:
        """获取策略状态(用于监控)"""
        return {
            "strategy_id": self.strategy_id,
            "underlying": self.underlying,
            "latest_p_vol": self.latest_p_vol,
            "latest_q_vol": self.latest_q_vol,
            "pq_spread": (self.latest_q_vol - self.latest_p_vol) if (self.latest_p_vol and self.latest_q_vol) else None,
            "current_position": self.current_position,
            "last_signal_time": self.last_signal_time.isoformat() if self.last_signal_time else None
        }
