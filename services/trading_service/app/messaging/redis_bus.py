from __future__ import annotations

import json
from typing import AsyncIterator, Dict, Optional

import redis.asyncio as redis

from app.messaging.message_bus import MessageBus


class RedisStreamBus(MessageBus):
    """基于 Redis Streams 的消息总线实现."""

    def __init__(
        self,
        client: redis.Redis,
        stream_prefix: str = "glm",
        group_name: str = "trading_service",
        consumer_name: str = "engine",
    ) -> None:
        self._client = client
        self._stream_prefix = stream_prefix
        self._group_name = group_name
        self._consumer_name = consumer_name

    @classmethod
    def from_url(
        cls,
        url: str,
        stream_prefix: str = "glm",
        group_name: str = "trading_service",
        consumer_name: str = "engine",
    ) -> "RedisStreamBus":
        client = redis.from_url(url)
        return cls(client, stream_prefix, group_name, consumer_name)

    def _stream(self, name: str) -> str:
        return f"{self._stream_prefix}:{name}"

    async def publish(self, stream: str, payload: Dict) -> None:
        stream_name = self._stream(stream)
        await self._client.xadd(stream_name, {"data": json.dumps(payload)})

    async def subscribe(self, stream: str) -> AsyncIterator[Dict]:
        stream_name = self._stream(stream)
        await self._ensure_group(stream_name)
        last_id = "0-0"
        while True:
            response = await self._client.xreadgroup(
                groupname=self._group_name,
                consumername=self._consumer_name,
                streams={stream_name: last_id},
                count=1,
                block=5000,
            )
            if not response:
                continue
            for _, messages in response:
                for message_id, data in messages:
                    raw = data.get(b"data", b"{}")
                    last_id = message_id
                    try:
                        yield json.loads(raw)
                        await self._client.xack(stream_name, self._group_name, message_id)
                    except json.JSONDecodeError:
                        await self._client.xack(stream_name, self._group_name, message_id)

    async def _ensure_group(self, stream_name: str) -> None:
        try:
            await self._client.xgroup_create(stream_name, self._group_name, id="0-0", mkstream=True)
        except redis.ResponseError as exc:  # 已存在group
            if "BUSYGROUP" not in str(exc):
                raise

    async def close(self) -> None:
        await self._client.close()

    async def subscribe_multiple(self, streams: list[str]) -> AsyncIterator[Dict]:
        """同时订阅多个流"""
        stream_map = {self._stream(s): "0-0" for s in streams}
        
        # 确保所有 group 存在
        for s in stream_map:
            await self._ensure_group(s)
            
        while True:
            response = await self._client.xreadgroup(
                groupname=self._group_name,
                consumername=self._consumer_name,
                streams=stream_map,
                count=10,
                block=2000,
            )
            
            if not response:
                yield {"type": "ping", "timestamp": "keep-alive"}
                continue
                
            for stream_name, messages in response:
                # 解析流名称，去掉前缀
                stream_key = stream_name.decode("utf-8").replace(f"{self._stream_prefix}:", "")
                
                for message_id, data in messages:
                    raw = data.get(b"data", b"{}")
                    try:
                        payload = json.loads(raw)
                        # 注入事件类型
                        payload["event_type"] = stream_key
                        yield payload
                        
                        # 确认消息
                        await self._client.xack(stream_name, self._group_name, message_id)
                    except json.JSONDecodeError:
                        await self._client.xack(stream_name, self._group_name, message_id)
