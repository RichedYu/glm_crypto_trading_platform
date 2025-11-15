from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Literal, List

from pydantic import BaseModel, Field


class MarketTickEvent(BaseModel):
    """市场行情tick事件"""
    symbol: str
    price: float
    volume: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StrategySignalEvent(BaseModel):
    """策略信号事件"""
    strategy_id: str
    signal_type: Literal["buy", "sell", "hold", "close"]
    symbol: str
    confidence: float = 1.0
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StrategyIntentEvent(BaseModel):
    """策略高级意图事件,由策略层输出"""
    intent_id: str
    strategy_id: str
    symbol: str
    intent_type: str
    action: str
    direction: Optional[Literal["buy", "sell"]] = None
    quantity: float = 0.0
    confidence: float = 1.0
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExecutionCommandEvent(BaseModel):
    """风控通过后的执行指令,由 StrategyEngine 发布"""
    intent_id: str
    strategy_id: str
    symbol: str
    action: str
    direction: Optional[Literal["buy", "sell"]] = None
    quantity: float = 0.0
    approved_by: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrderCommand(BaseModel):
    """订单命令"""
    strategy_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"] = "limit"
    quantity: float
    price: Optional[float] = None
    command: Literal["create", "cancel", "modify"] = "create"
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderFillEvent(BaseModel):
    """订单成交事件"""
    strategy_id: str
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    fee: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAlertEvent(BaseModel):
    """风险告警事件"""
    strategy_id: str
    alert_type: Literal["position_limit", "loss_limit", "volatility", "liquidity"]
    severity: Literal["info", "warning", "critical"]
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StateSnapshotEvent(BaseModel):
    """状态快照事件"""
    strategy_id: str
    state_type: Literal["position", "balance", "orders", "full"]
    snapshot: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PositionUpdateEvent(BaseModel):
    """持仓更新事件"""
    strategy_id: str
    symbol: str
    quantity: float
    avg_price: float
    unrealized_pnl: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OptionGreeks(BaseModel):
    """期权Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class OptionChainData(BaseModel):
    """期权链数据"""
    underlying: str  # 标的资产
    strike: float  # 行权价
    expiry: str  # 到期日
    option_type: Literal["call", "put"]
    bid: float
    ask: float
    last: float
    volume: float
    open_interest: float
    implied_volatility: float  # 隐含波动率(P-World)
    greeks: Optional[OptionGreeks] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VolatilitySurfaceEvent(BaseModel):
    """波动率曲面事件(P-World)"""
    underlying: str
    surface_data: List[OptionChainData]  # 所有期权合约
    atm_iv: float  # 平值隐含波动率
    iv_skew: Dict[str, float]  # 波动率偏斜 {strike: iv}
    term_structure: Dict[str, float]  # 期限结构 {expiry: iv}
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VolatilityForecastEvent(BaseModel):
    """波动率预测事件(Q-World)"""
    underlying: str
    forecast_horizon: str  # 预测时间范围 "1h", "24h", "7d"
    predicted_volatility: float  # 预测波动率
    confidence: float  # 置信度
    model_version: str
    features_used: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MacroStateEvent(BaseModel):
    """宏观 / 情绪 状态广播事件"""
    symbol: Optional[str] = None
    macro_regime: Optional[str] = None
    regime_score: float = 0.0
    sentiment_score: Optional[float] = None
    fomo_score: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioRiskEvent(BaseModel):
    """组合风险/Greeks 广播事件"""
    total_delta: float
    total_gamma: float
    total_vega: float
    total_theta: float
    total_rho: float
    position_ratio: Optional[float] = None
    leverage: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
