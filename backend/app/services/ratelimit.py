"""Rate limiting (DB/doc 8-point checklist item 6).

In-memory sliding window; Phase 2 replaces this with Redis without changing
call sites. Applied as a FastAPI dependency on sensitive endpoints.
"""
from __future__ import annotations

import time
from collections import deque

from fastapi import Request

from app.config import get_settings
from app.errors import RateLimitedError

_WINDOW_SECONDS = 60
_buckets: dict[str, deque[float]] = {}


def enforce_rate_limit(request: Request, bucket: str, limit: int | None = None) -> None:
    settings = get_settings()
    effective = limit if limit is not None else settings.rate_limit_per_minute
    client = request.client.host if request.client else "unknown"
    key = f"{bucket}:{client}"
    now = time.monotonic()
    window = _buckets.setdefault(key, deque())
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= effective:
        raise RateLimitedError(
            "Too many requests. Please slow down.",
            details={"bucket": bucket, "limit_per_minute": effective},
        )
    window.append(now)


def reset_rate_limits() -> None:
    _buckets.clear()
