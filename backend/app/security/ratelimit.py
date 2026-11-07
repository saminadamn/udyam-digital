"""Small in-memory sliding-window rate limiter (single API instance, as deployed for the demo). A restart clears it; for several
instances put the same interface on Redis."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.errors import ApiError

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def hit(key: str, limit: int, window_s: int, message: str = "Too many requests. Please try again in a few minutes.") -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_s - (now - q[0])) + 1
            raise ApiError(429, "RATE_LIMITED", message, {"retry_after_s": retry})
        q.append(now)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def reset() -> None:
    with _lock:
        _hits.clear()
