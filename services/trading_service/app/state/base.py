from __future__ import annotations

import abc
from typing import Any, Dict, Optional


class StateStore(abc.ABC):
    """统一的策略状态存储接口."""

    @abc.abstractmethod
    async def set_strategy_state(self, strategy_id: str, state: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_strategy_state(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def append_event(self, strategy_id: str, event: Dict[str, Any]) -> None:
        raise NotImplementedError
