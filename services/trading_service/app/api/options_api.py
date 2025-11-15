from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.state.portfolio_store import PortfolioStateStore
from app.messaging.redis_bus import RedisStreamBus

router = APIRouter(prefix="/api/v1/options", tags=["期权交易"])


# 全局实例(实际应通过依赖注入)
portfolio_store: Optional[PortfolioStateStore] = None
message_bus: Optional[RedisStreamBus] = None


def init_options_api(store: PortfolioStateStore, bus: RedisStreamBus):
    """初始化API依赖"""
    global portfolio_store, message_bus
    portfolio_store = store
    message_bus = bus


@router.get("/volatility-surface/{underlying}")
async def get_volatility_surface(underlying: str):
    """
    获取波动率曲面(P-World)
    
    返回最新的期权链数据和隐含波动率
    """
    # TODO: 从Redis或缓存获取最新波动率曲面
    return {
        "underlying": underlying,
        "atm_iv": 0.65,
        "timestamp": datetime.utcnow().isoformat(),
        "surface_data": [
            {
                "strike": 40000,
                "expiry": "2024-12-29",
                "call_iv": 0.68,
                "put_iv": 0.62,
                "call_price": 2500,
                "put_price": 2300
            }
        ]
    }


@router.get("/pq-spread/{underlying}")
async def get_pq_spread(underlying: str):
    """
    获取P-Q价差
    
    P: 市场隐含波动率
    Q: 模型预测波动率
    """
    # TODO: 从Redis获取最新P和Q值
    intent_type = "increase_long_gamma"
    intent_reason = "market_underpricing_volatility"
    macro_regime = "bull"
    regime_score = 0.58
    fomo_score = 0.32

    return {
        "underlying": underlying,
        "p_vol": 0.65,
        "q_vol": 0.72,
        "spread": 0.07,
        "signal": "buy_volatility",
        "confidence": 0.85,
        "intent_type": intent_type,
        "intent_reason": intent_reason,
        "macro_regime": macro_regime,
        "regime_score": regime_score,
        "fomo_score": fomo_score,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/greeks/portfolio")
async def get_portfolio_greeks():
    """
    获取投资组合总Greeks
    
    用于Delta对冲监控
    """
    if not portfolio_store:
        raise HTTPException(status_code=503, detail="Portfolio store not initialized")
    
    try:
        risk_metrics = await portfolio_store.get_risk_metrics()
        
        return {
            "total_delta": risk_metrics.get("total_delta", 0.0),
            "total_gamma": risk_metrics.get("total_gamma", 0.0),
            "total_vega": risk_metrics.get("total_vega", 0.0),
            "total_theta": risk_metrics.get("total_theta", 0.0),
            "total_rho": risk_metrics.get("total_rho", 0.0),
            "timestamp": risk_metrics.get("updated_at"),
            "hedge_status": "neutral" if abs(risk_metrics.get("total_delta", 0)) < 0.05 else "needs_hedge"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/options")
async def get_option_positions():
    """获取期权持仓"""
    if not portfolio_store:
        raise HTTPException(status_code=503, detail="Portfolio store not initialized")
    
    try:
        positions = await portfolio_store.get_all_positions()
        
        # 筛选期权持仓
        option_positions = []
        for symbol, pos in positions.items():
            if "-C" in symbol or "-P" in symbol:  # 期权合约标识
                option_positions.append({
                    "symbol": symbol,
                    "quantity": pos["quantity"],
                    "avg_price": pos["avg_price"],
                    "unrealized_pnl": pos.get("unrealized_pnl", 0),
                    "greeks": pos.get("greeks", {}),
                    "strategy_id": pos.get("strategy_id")
                })
        
        return {
            "positions": option_positions,
            "total_count": len(option_positions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hedge/status")
async def get_hedge_status():
    """
    获取Delta对冲状态
    
    用于Gamma Scalping监控
    """
    if not portfolio_store:
        raise HTTPException(status_code=503, detail="Portfolio store not initialized")
    
    try:
        risk_metrics = await portfolio_store.get_risk_metrics()
        total_delta = risk_metrics.get("total_delta", 0.0)
        
        # 判断对冲状态
        if abs(total_delta) < 0.02:
            status = "well_hedged"
            action = "none"
        elif total_delta > 0.05:
            status = "long_delta"
            action = "sell_futures"
        elif total_delta < -0.05:
            status = "short_delta"
            action = "buy_futures"
        else:
            status = "acceptable"
            action = "monitor"
        
        return {
            "total_delta": total_delta,
            "status": status,
            "recommended_action": action,
            "hedge_quantity": abs(total_delta) if abs(total_delta) > 0.05 else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/pq-trader/state")
async def get_pq_trader_state():
    """获取P vs Q策略状态"""
    # TODO: 从策略引擎获取状态
    return {
        "strategy_id": "pq_vol_trader_1",
        "status": "active",
        "latest_p_vol": 0.65,
        "latest_q_vol": 0.72,
        "pq_spread": 0.07,
        "current_position": 1.5,
        "last_signal_time": datetime.utcnow().isoformat(),
        "pnl": 1250.50
    }


@router.get("/strategies/delta-hedger/state")
async def get_delta_hedger_state():
    """获取Delta对冲策略状态"""
    # TODO: 从策略引擎获取状态
    return {
        "strategy_id": "delta_hedger_1",
        "status": "active",
        "current_total_delta": 0.03,
        "hedge_position": -0.03,
        "last_hedge_time": datetime.utcnow().isoformat(),
        "hedge_count_today": 12
    }
