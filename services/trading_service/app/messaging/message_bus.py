from __future__ import annotations

import abc
from typing import AsyncIterator, Dict, Protocol


class MessageBus(abc.ABC):
    """抽象消息总线，定义发布/订阅接口."""

    @abc.abstractmethod
    async def publish(self, stream: str, payload: Dict) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def subscribe(self, stream: str) -> AsyncIterator[Dict]:
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class BusFactory(Protocol):
    async def __call__(self) -> MessageBus: ...
