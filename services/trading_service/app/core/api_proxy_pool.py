from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Iterable, List, Dict, Any, Optional

import aiohttp


@dataclass
class ProxyEndpoint:
    base_url: str
    failure_count: int = 0
    unhealthy_until: float = 0.0

    def normalized(self) -> str:
        return self.base_url.rstrip("/")


class ApiProxyPool:
    """
    Simple async-aware proxy pool that rotates through multiple API base URLs.

    Features:
      - Round-robin load balancing with cooldown after repeated failures
      - In-memory health tracking for each endpoint
      - JSON helper for services that speak REST style APIs
    """

    def __init__(
        self,
        service_name: str,
        endpoints: Iterable[str],
        timeout: float = 10.0,
        failure_threshold: int = 2,
        cooldown: int = 120,
    ) -> None:
        unique_endpoints: List[ProxyEndpoint] = []
        seen: set[str] = set()

        for endpoint in endpoints:
            if not endpoint:
                continue
            normalized = endpoint.rstrip("/")
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_endpoints.append(ProxyEndpoint(normalized))

        if not unique_endpoints:
            raise ValueError("ApiProxyPool requires at least one valid endpoint")

        self._service_name = service_name
        self._endpoints = unique_endpoints
        self._cursor = 0
        self._lock = asyncio.Lock()
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.logger = logging.getLogger(f"ApiProxyPool[{service_name}]")

    async def request_json(
        self,
        method: str,
        path: str = "",
        *,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Send an HTTP request to the healthiest endpoint and parse JSON response.
        """
        last_error: Optional[Exception] = None
        attempts = 0
        total = len(self._endpoints)

        while attempts < total:
            endpoint = await self._get_next_endpoint()
            url = self._build_url(endpoint, path)
            try:
                payload = await self._request_json_from_endpoint(
                    endpoint,
                    method,
                    url,
                    timeout or self.timeout,
                    **kwargs,
                )
                self._register_success(endpoint)
                return payload
            except Exception as exc:  # noqa: BLE001
                self._register_failure(endpoint, exc)
                last_error = exc
                attempts += 1

        raise RuntimeError(f"All endpoints failed for {self._service_name}") from last_error

    async def _request_json_from_endpoint(
        self,
        endpoint: ProxyEndpoint,
        method: str,
        url: str,
        timeout: float,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.request(method.upper(), url, **kwargs) as response:
                response.raise_for_status()
                json_payload = await response.json()
                self.logger.debug(
                    "Request to %s succeeded (status=%s)",
                    endpoint.base_url,
                    response.status,
                )
                return json_payload

    async def _get_next_endpoint(self) -> ProxyEndpoint:
        async with self._lock:
            now = time.time()
            total = len(self._endpoints)

            for _ in range(total):
                endpoint = self._endpoints[self._cursor]
                self._cursor = (self._cursor + 1) % total
                if endpoint.unhealthy_until <= now:
                    return endpoint

            # 如果全部处于冷却期，返回最早可用的那个
            return min(self._endpoints, key=lambda ep: ep.unhealthy_until)

    def _register_failure(self, endpoint: ProxyEndpoint, exc: Exception) -> None:
        endpoint.failure_count += 1
        self.logger.warning(
            "Endpoint %s failed (%s/%s): %s",
            endpoint.base_url,
            endpoint.failure_count,
            self.failure_threshold,
            exc,
        )
        if endpoint.failure_count >= self.failure_threshold:
            endpoint.unhealthy_until = time.time() + self.cooldown
            endpoint.failure_count = 0
            self.logger.error(
                "Endpoint %s marked unhealthy for %ss",
                endpoint.base_url,
                self.cooldown,
            )

    @staticmethod
    def _build_url(endpoint: ProxyEndpoint, path: str) -> str:
        if not path:
            return endpoint.normalized()
        return f"{endpoint.normalized()}/{path.lstrip('/')}"

    def _register_success(self, endpoint: ProxyEndpoint) -> None:
        endpoint.failure_count = 0
        endpoint.unhealthy_until = 0.0

    def health_snapshot(self) -> List[Dict[str, Any]]:
        """
        Return current health status for observability / debugging.
        """
        now = time.time()
        return [
            {
                "base_url": endpoint.base_url,
                "available": endpoint.unhealthy_until <= now,
                "cooldown_remaining": max(0.0, endpoint.unhealthy_until - now),
            }
            for endpoint in self._endpoints
        ]
