from __future__ import annotations

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal

import redis.asyncio as redis


class PortfolioStateStore:
    """全局投资组合状态存储 - 用于风控"""

    def __init__(
        self,
        client: redis.Redis,
        key_prefix: str = "glm:portfolio",
        ttl: int = 86400 * 30  # 30天过期
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._ttl = ttl

    @classmethod
    def from_url(
        cls,
        url: str,
        key_prefix: str = "glm:portfolio",
        ttl: int = 86400 * 30
    ) -> "PortfolioStateStore":
        client = redis.from_url(url)
        return cls(client, key_prefix, ttl)

    def _global_balance_key(self) -> str:
        """全局余额键"""
        return f"{self._key_prefix}:balance"

    def _global_positions_key(self) -> str:
        """全局持仓键"""
        return f"{self._key_prefix}:positions"

    def _pnl_history_key(self) -> str:
        """PnL历史键"""
        return f"{self._key_prefix}:pnl_history"

    def _risk_metrics_key(self) -> str:
        """风险指标键"""
        return f"{self._key_prefix}:risk_metrics"

    def _drawdown_key(self) -> str:
        """回撤记录键"""
        return f"{self._key_prefix}:drawdown"

    async def update_global_balance(
        self,
        balances: Dict[str, float]
    ) -> None:
        """
        更新全局余额
        
        Args:
            balances: 资产余额字典 {"USDT": 1000.0, "BNB": 10.5}
        """
        key = self._global_balance_key()
        balance_data = {
            **balances,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(
            key,
            mapping={k: json.dumps(v) for k, v in balance_data.items()}
        )
        await self._client.expire(key, self._ttl)

    async def get_global_balance(self) -> Dict[str, float]:
        """获取全局余额"""
        key = self._global_balance_key()
        data = await self._client.hgetall(key)
        if not data:
            return {}
        
        result = {}
        for k, v in data.items():
            k_str = k.decode()
            if k_str != "updated_at":
                result[k_str] = json.loads(v)
        return result

    async def update_position(
        self,
        symbol: str,
        quantity: float,
        avg_price: float,
        unrealized_pnl: float = 0.0,
        strategy_id: Optional[str] = None
    ) -> None:
        """
        更新全局持仓
        
        Args:
            symbol: 交易对
            quantity: 持仓数量
            avg_price: 平均价格
            unrealized_pnl: 未实现盈亏
            strategy_id: 策略ID(可选)
        """
        key = self._global_positions_key()
        position = {
            "symbol": symbol,
            "quantity": quantity,
            "avg_price": avg_price,
            "unrealized_pnl": unrealized_pnl,
            "strategy_id": strategy_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(key, symbol, json.dumps(position))
        await self._client.expire(key, self._ttl)

    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单个持仓"""
        key = self._global_positions_key()
        data = await self._client.hget(key, symbol)
        if not data:
            return None
        return json.loads(data)

    async def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有持仓"""
        key = self._global_positions_key()
        data = await self._client.hgetall(key)
        return {k.decode(): json.loads(v) for k, v in data.items()}

    async def record_pnl(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
        total_value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录PnL快照
        
        Args:
            realized_pnl: 已实现盈亏
            unrealized_pnl: 未实现盈亏
            total_value: 总资产价值
            metadata: 额外元数据
        """
        key = self._pnl_history_key()
        pnl_record = {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": realized_pnl + unrealized_pnl,
            "total_value": total_value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        await self._client.rpush(key, json.dumps(pnl_record))
        # 保持最近10000条记录
        await self._client.ltrim(key, -10000, -1)
        await self._client.expire(key, self._ttl)

    async def get_recent_pnl(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的PnL记录"""
        key = self._pnl_history_key()
        data = await self._client.lrange(key, -limit, -1)
        return [json.loads(item) for item in data]

    async def update_risk_metrics(
        self,
        metrics: Dict[str, Any]
    ) -> None:
        """
        更新风险指标
        
        Args:
            metrics: 风险指标字典
                - total_exposure: 总敞口
                - position_ratio: 仓位比例
                - leverage: 杠杆倍数
                - var: 风险价值
                - max_drawdown: 最大回撤
                - total_delta: 总Delta敞口 (用于Delta对冲)
                - total_gamma: 总Gamma
                - total_vega: 总Vega
                等
        """
        key = self._risk_metrics_key()
        metrics_with_ts = {
            **metrics,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(
            key,
            mapping={k: json.dumps(v) for k, v in metrics_with_ts.items()}
        )
        await self._client.expire(key, self._ttl)
        
        # 如果total_delta变化,发布事件通知DeltaHedger
        if "total_delta" in metrics:
            await self._publish_delta_change(metrics["total_delta"])
    
    async def _publish_delta_change(self, total_delta: float) -> None:
        """发布Delta变化事件(用于触发DeltaHedger)"""
        # 注意: 这需要message_bus实例,实际实现时需要注入
        # 这里先预留接口
        pass

    async def get_risk_metrics(self) -> Dict[str, Any]:
        """获取当前风险指标"""
        key = self._risk_metrics_key()
        data = await self._client.hgetall(key)
        if not data:
            return {}
        return {k.decode(): json.loads(v) for k, v in data.items()}

    async def record_drawdown(
        self,
        current_value: float,
        peak_value: float,
        drawdown_pct: float
    ) -> None:
        """
        记录回撤
        
        Args:
            current_value: 当前资产价值
            peak_value: 峰值资产价值
            drawdown_pct: 回撤百分比
        """
        key = self._drawdown_key()
        drawdown_record = {
            "current_value": current_value,
            "peak_value": peak_value,
            "drawdown_pct": drawdown_pct,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._client.rpush(key, json.dumps(drawdown_record))
        # 保持最近1000条记录
        await self._client.ltrim(key, -1000, -1)
        await self._client.expire(key, self._ttl)

    async def get_current_drawdown(self) -> Optional[Dict[str, Any]]:
        """获取当前回撤"""
        key = self._drawdown_key()
        data = await self._client.lrange(key, -1, -1)
        if not data:
            return None
        return json.loads(data[0])

    async def get_peak_value(self) -> float:
        """获取历史峰值"""
        pnl_history = await self.get_recent_pnl(limit=10000)
        if not pnl_history:
            return 0.0
        return max(record["total_value"] for record in pnl_history)

    async def get_total_delta(self) -> float:
        """获取当前总Delta敞口"""
        metrics = await self.get_risk_metrics()
        return metrics.get("total_delta", 0.0)
    
    async def update_position_greeks(
        self,
        symbol: str,
        greeks: Dict[str, float]
    ) -> None:
        """
        更新持仓的Greeks
        
        Args:
            symbol: 交易对/合约
            greeks: Greeks字典 {delta, gamma, theta, vega, rho}
        """
        position = await self.get_position(symbol)
        if position:
            position["greeks"] = greeks
            await self.update_position(
                symbol=symbol,
                quantity=position["quantity"],
                avg_price=position["avg_price"],
                unrealized_pnl=position.get("unrealized_pnl", 0.0),
                strategy_id=position.get("strategy_id")
            )

    async def close(self) -> None:
        """关闭连接"""
        await self._client.close()