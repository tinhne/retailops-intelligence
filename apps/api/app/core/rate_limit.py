"""In-process sliding-window rate limiter.

Limitation (documented in SECURITY_ARCHITECTURE.md): state is per process. Running several API
instances needs a shared store such as Redis.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimitedError


class SlidingWindowRateLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, *, now: float | None = None) -> None:
        """Record one event for ``key``; raise RateLimitedError if the window is full."""
        current = time.monotonic() if now is None else now
        with self._lock:
            events = self._events[key]
            while events and current - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.max_events:
                retry_after = max(1, int(self.window_seconds - (current - events[0])) + 1)
                raise RateLimitedError(
                    "Too many requests. Please retry later.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(current)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
