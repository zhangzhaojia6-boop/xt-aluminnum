from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int


class SlidingWindowRateLimiter:
    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def consume(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> RateLimitDecision:
        current = float(time.monotonic() if now is None else now)
        window = max(1, int(window_seconds))
        max_requests = max(1, int(limit))

        with self._lock:
            bucket = self._events[key]
            cutoff = current - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_requests:
                retry_after = max(1, math.ceil(bucket[0] + window - current))
                return RateLimitDecision(allowed=False, retry_after=retry_after)

            bucket.append(current)
            return RateLimitDecision(allowed=True, retry_after=0)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class ConnectionPermit:
    def __init__(self, limiter: 'ConcurrentConnectionLimiter', key: str):
        self._limiter = limiter
        self._key = key
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._limiter.release(self._key)


class ConcurrentConnectionLimiter:
    def __init__(self):
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def acquire(self, key: str, *, limit: int) -> ConnectionPermit | None:
        max_connections = max(1, int(limit))
        with self._lock:
            if self._counts[key] >= max_connections:
                return None
            self._counts[key] += 1
        return ConnectionPermit(self, key)

    def release(self, key: str) -> None:
        with self._lock:
            current = self._counts.get(key, 0)
            if current <= 1:
                self._counts.pop(key, None)
                return
            self._counts[key] = current - 1

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


request_rate_limiter = SlidingWindowRateLimiter()
connection_rate_limiter = ConcurrentConnectionLimiter()


def _subject_for_request(request: Request, current_user) -> str:
    user_id = getattr(current_user, 'id', None)
    if user_id is not None:
        return f'user:{user_id}'
    client_host = request.client.host if request.client else 'unknown'
    return f'ip:{client_host}'


def _rate_limit_error(*, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail='Rate limit exceeded',
        headers={'Retry-After': str(max(1, int(retry_after)))},
    )


def enforce_request_rate_limit(
    request: Request,
    current_user,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
) -> None:
    subject = _subject_for_request(request, current_user)
    decision = request_rate_limiter.consume(
        f'{subject}:{scope}',
        limit=limit,
        window_seconds=window_seconds,
    )
    if not decision.allowed:
        raise _rate_limit_error(retry_after=decision.retry_after)


def acquire_connection_rate_limit(
    request: Request,
    current_user,
    *,
    scope: str,
    limit: int,
) -> ConnectionPermit:
    subject = _subject_for_request(request, current_user)
    permit = connection_rate_limiter.acquire(f'{subject}:{scope}', limit=limit)
    if permit is None:
        raise _rate_limit_error(retry_after=1)
    return permit


def reset_rate_limits() -> None:
    request_rate_limiter.reset()
    connection_rate_limiter.reset()
