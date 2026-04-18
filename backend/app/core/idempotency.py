from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    key: str
    fingerprint: str
    value: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class InMemoryIdempotencyStore:
    def __init__(self, *, default_ttl_seconds: int = 24 * 60 * 60):
        self._default_ttl_seconds = max(1, int(default_ttl_seconds))
        self._items: dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = Lock()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _purge_expired(self, *, now: datetime) -> None:
        expired_keys = [key for key, record in self._items.items() if record.expires_at <= now]
        for key in expired_keys:
            self._items.pop(key, None)

    def get(self, *, scope: str, key: str, now: datetime | None = None) -> IdempotencyRecord | None:
        current_time = now or self._now()
        with self._lock:
            self._purge_expired(now=current_time)
            return self._items.get((scope, key))

    def put(
        self,
        *,
        scope: str,
        key: str,
        fingerprint: str,
        value: dict[str, Any],
        ttl_seconds: int | None = None,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        current_time = now or self._now()
        ttl = max(1, int(ttl_seconds or self._default_ttl_seconds))
        record = IdempotencyRecord(
            scope=scope,
            key=key,
            fingerprint=fingerprint,
            value=dict(value),
            created_at=current_time,
            expires_at=current_time + timedelta(seconds=ttl),
        )
        with self._lock:
            self._purge_expired(now=current_time)
            self._items[(scope, key)] = record
        return record

    def delete(self, *, scope: str, key: str) -> None:
        with self._lock:
            self._items.pop((scope, key), None)


work_order_entry_idempotency_store = InMemoryIdempotencyStore()
