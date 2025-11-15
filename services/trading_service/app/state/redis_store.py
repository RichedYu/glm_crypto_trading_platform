from __future__ import annotations

import json
from typing import Any, Dict, Optional, List
from datetime import datetime

import redis.asyncio as redis

from app.state.base import StateStore


class RedisStateStore(StateStore):
    """基于Redis的状态存储实现"""

    def __init__(
        self,
        client: redis.Redis,
        key_prefix: str = "glm:state",
        ttl: int = 86400 * 7  # 7天过期
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._ttl = ttl

    @classmethod
    def from_url(
        cls,
        url: str,
        key_prefix: str = "glm:state",
        ttl: int = 86400 * 7
    ) -> "RedisStateStore":
        client = redis.from_url(url)
        return cls(client, key_prefix, ttl)

    def _strategy_key(self, strategy_id: str) -> str:
        """策略状态键"""
        return f"{self._key_prefix}:strategy:{strategy_id}"

    def _position_key(self, strategy_id: str) -> str:
        """持仓键"""
        return f"{self._key_prefix}:position:{strategy_id}"

    def _balance_key(self, strategy_id: str) -> str:
        """余额键"""
        return f"{self._key_prefix}:balance:{strategy_id}"

    def _orders_key(self, strategy_id: str) -> str:
        """订单键"""
        return f"{self._key_prefix}:orders:{strategy_id}"

    def _events_key(self, strategy_id: str) -> str:
        """事件流键"""
        return f"{self._key_prefix}:events:{strategy_id}"

    async def set_strategy_state(self, strategy_id: str, state: Dict[str, Any]) -> None:
        """设置策略完整状态"""
        key = self._strategy_key(strategy_id)
        state_with_ts = {
            **state,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(
            key,
            mapping={k: json.dumps(v) for k, v in state_with_ts.items()}
        )
        await self._client.expire(key, self._ttl)

    async def get_strategy_state(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取策略完整状态"""
        key = self._strategy_key(strategy_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        return {k.decode(): json.loads(v) for k, v in data.items()}

    async def set_position(
        self,
        strategy_id: str,
        symbol: str,
        quantity: float,
        avg_price: float,
        unrealized_pnl: float = 0.0
    ) -> None:
        """设置持仓"""
        key = self._position_key(strategy_id)
        position = {
            "symbol": symbol,
            "quantity": quantity,
            "avg_price": avg_price,
            "unrealized_pnl": unrealized_pnl,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(key, symbol, json.dumps(position))
        await self._client.expire(key, self._ttl)

    async def get_position(self, strategy_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """获取持仓"""
        key = self._position_key(strategy_id)
        data = await self._client.hget(key, symbol)
        if not data:
            return None
        return json.loads(data)

    async def get_all_positions(self, strategy_id: str) -> Dict[str, Dict[str, Any]]:
        """获取所有持仓"""
        key = self._position_key(strategy_id)
        data = await self._client.hgetall(key)
        return {k.decode(): json.loads(v) for k, v in data.items()}

    async def set_balance(
        self,
        strategy_id: str,
        balances: Dict[str, float]
    ) -> None:
        """设置余额"""
        key = self._balance_key(strategy_id)
        balance_data = {
            **balances,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(
            key,
            mapping={k: json.dumps(v) for k, v in balance_data.items()}
        )
        await self._client.expire(key, self._ttl)

    async def get_balance(self, strategy_id: str) -> Dict[str, float]:
        """获取余额"""
        key = self._balance_key(strategy_id)
        data = await self._client.hgetall(key)
        if not data:
            return {}
        result = {}
        for k, v in data.items():
            k_str = k.decode()
            if k_str != "updated_at":
                result[k_str] = json.loads(v)
        return result

    async def add_order(
        self,
        strategy_id: str,
        order_id: str,
        order_data: Dict[str, Any]
    ) -> None:
        """添加订单"""
        key = self._orders_key(strategy_id)
        order_with_ts = {
            **order_data,
            "created_at": datetime.utcnow().isoformat()
        }
        await self._client.hset(key, order_id, json.dumps(order_with_ts))
        await self._client.expire(key, self._ttl)

    async def get_order(self, strategy_id: str, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单"""
        key = self._orders_key(strategy_id)
        data = await self._client.hget(key, order_id)
        if not data:
            return None
        return json.loads(data)

    async def get_all_orders(self, strategy_id: str) -> Dict[str, Dict[str, Any]]:
        """获取所有订单"""
        key = self._orders_key(strategy_id)
        data = await self._client.hgetall(key)
        return {k.decode(): json.loads(v) for k, v in data.items()}

    async def remove_order(self, strategy_id: str, order_id: str) -> None:
        """删除订单"""
        key = self._orders_key(strategy_id)
        await self._client.hdel(key, order_id)

    async def append_event(self, strategy_id: str, event: Dict[str, Any]) -> None:
        """追加事件到事件流"""
        key = self._events_key(strategy_id)
        event_with_ts = {
            **event,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._client.rpush(key, json.dumps(event_with_ts))
        # 保持最近1000条事件
        await self._client.ltrim(key, -1000, -1)
        await self._client.expire(key, self._ttl)

    async def get_recent_events(
        self,
        strategy_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取最近的事件"""
        key = self._events_key(strategy_id)
        data = await self._client.lrange(key, -limit, -1)
        return [json.loads(item) for item in data]

    async def close(self) -> None:
        """关闭连接"""
        await self._client.close()