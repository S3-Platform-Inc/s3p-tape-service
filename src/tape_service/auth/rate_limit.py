from __future__ import annotations

import threading
import time
from collections import deque


class TokenBucket:
    """Fixed-window per-key counter, threadsafe and in-process.

    Use it as a single instance per FastAPI app to throttle a hot
    endpoint (e.g. /auth/login) by client IP. Sized for a single web
    replica behind the reverse proxy — there is no shared state across
    replicas. If we ever scale the api beyond one instance we move
    this to Redis (INCR + EXPIRE).
    """

    def __init__(self, capacity: int, window_seconds: float) -> None:
        self.capacity = capacity
        self.window = window_seconds
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._events.setdefault(key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.capacity:
                return False
            q.append(now)
            return True
