from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from etf_timing.data.cache import CacheRecord, SQLiteCache
from etf_timing.data.provider import MarketDataProvider


@dataclass(frozen=True, slots=True)
class Dataset:
    data: Any
    meta: dict[str, Any]


class DataGateway:
    def __init__(
        self,
        cache: SQLiteCache,
        live_provider: MarketDataProvider,
        sample_provider: MarketDataProvider,
        mode: str,
    ) -> None:
        self.cache = cache
        self.live_provider = live_provider
        self.sample_provider = sample_provider
        self.mode = mode
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._source_state: dict[str, dict[str, Any]] = {}
        self._source_state_guard = threading.Lock()

    def _key_lock(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

    @staticmethod
    def _meta(record: CacheRecord, status: str, message: str | None = None) -> dict[str, Any]:
        return {
            "source": record.source,
            "status": status,
            "asOf": record.fetched_at.isoformat(),
            "expiresAt": record.expires_at.isoformat(),
            "message": message,
        }

    def load(
        self,
        *,
        key: str,
        ttl_seconds: int,
        live_loader: Callable[[], Any],
        sample_loader: Callable[[], Any],
        refresh: bool = False,
        live_loaders: list[tuple[str, Callable[[], Any]]] | None = None,
    ) -> Dataset:
        cached = self.cache.get(key)
        if cached and cached.is_fresh and not refresh:
            status = "sample" if cached.source == self.sample_provider.name else "cached"
            return Dataset(cached.payload, self._meta(cached, status))

        with self._key_lock(key):
            cached = self.cache.get(key)
            if cached and cached.is_fresh and not refresh:
                status = "sample" if cached.source == self.sample_provider.name else "cached"
                return Dataset(cached.payload, self._meta(cached, status))

            if self.mode == "sample":
                payload = sample_loader()
                record = self.cache.set(key, payload, ttl_seconds, self.sample_provider.name)
                return Dataset(payload, self._meta(record, "sample", "当前为离线示例模式"))

            last_error: Exception | None = None
            errors: list[str] = []
            sources = live_loaders or [(self.live_provider.name, live_loader)]
            for source_index, (source_name, source_loader) in enumerate(sources):
                try:
                    payload = source_loader()
                    if not payload:
                        raise ValueError(f"upstream returned empty dataset for {key}")
                    record = self.cache.set(key, payload, ttl_seconds, source_name)
                    self._record_source(source_name, True)
                    message = None
                    if source_index:
                        message = f"主数据源不可用，已切换至 {source_name}"
                    return Dataset(payload, self._meta(record, "live", message))
                except Exception as exc:  # upstream libraries raise heterogeneous errors
                    last_error = exc
                    errors.append(f"{source_name}:{type(exc).__name__}")
                    self._record_source(source_name, False, type(exc).__name__)
                    if source_index + 1 < len(sources):
                        time.sleep(0.15)

            if cached is not None:
                message = f"实时源不可用，已使用陈旧缓存：{', '.join(errors)}"
                return Dataset(cached.payload, self._meta(cached, "stale", message))

            if self.mode == "auto":
                payload = sample_loader()
                record = self.cache.set(
                    key,
                    payload,
                    min(ttl_seconds, 300),
                    self.sample_provider.name,
                )
                message = f"实时源不可用且无缓存，已使用示例数据：{type(last_error).__name__}"
                return Dataset(payload, self._meta(record, "sample", message))

            raise RuntimeError(f"Unable to load {key} from live provider") from last_error

    def _record_source(self, source: str, succeeded: bool, error: str | None = None) -> None:
        from etf_timing.data.cache import now_shanghai

        with self._source_state_guard:
            state = self._source_state.setdefault(
                source,
                {"successes": 0, "failures": 0, "lastSuccessAt": None, "lastErrorAt": None},
            )
            timestamp = now_shanghai().isoformat()
            if succeeded:
                state["successes"] += 1
                state["lastSuccessAt"] = timestamp
                state["lastError"] = None
            else:
                state["failures"] += 1
                state["lastErrorAt"] = timestamp
                state["lastError"] = error

    def source_health(self) -> dict[str, dict[str, Any]]:
        with self._source_state_guard:
            return {name: dict(state) for name, state in self._source_state.items()}
