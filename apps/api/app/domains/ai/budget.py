"""In-process guards on the live LLM provider (AI_ARCHITECTURE.md §4.2, §8.2).

``LLMBudget`` caps live LLM requests per minute and per UTC day, and tokens per UTC day, for this
API instance. It sits *below* the provider's free-tier quota so the product degrades to the
deterministic provider on its own terms instead of collecting 429s. ``CircuitBreaker`` stops
calling a provider after repeated failures, and for the provider's ``Retry-After`` after a quota
error (doubling on consecutive quota errors, up to one hour).

Limitation (documented in SAFETY_AND_LIMITATIONS.md §6): both are per process and reset on
restart; several instances would each spend their own budget against one shared quota.
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime

from app.domains.ai.models import FallbackReason

Clock = Callable[[], float]
_MAX_OPEN_SECONDS = 3600.0
_DEFAULT_RATE_LIMIT_OPEN = 60.0
_FAILURE_WINDOW = 60.0


def _utc_day(now: float) -> date:
    return datetime.fromtimestamp(now, tz=UTC).date()


class LLMBudget:
    def __init__(
        self,
        *,
        requests_per_minute: int,
        requests_per_day: int,
        tokens_per_day: int,
        clock: Clock = time.time,
    ) -> None:
        self._rpm = requests_per_minute
        self._rpd = requests_per_day
        self._tpd = tokens_per_day
        self._clock = clock
        self._lock = threading.Lock()
        self._minute: deque[float] = deque()
        self._day = _utc_day(clock())
        self._day_requests = 0
        self._day_tokens = 0

    def _roll(self, now: float) -> None:
        while self._minute and now - self._minute[0] >= 60:
            self._minute.popleft()
        today = _utc_day(now)
        if today != self._day:  # the day resets at 00:00 UTC
            self._day, self._day_requests, self._day_tokens = today, 0, 0

    def try_acquire(self) -> bool:
        """Reserve one live request; False when any window is spent."""
        with self._lock:
            now = self._clock()
            self._roll(now)
            if (
                len(self._minute) >= self._rpm
                or self._day_requests >= self._rpd
                or self._day_tokens >= self._tpd
            ):
                return False
            self._minute.append(now)
            self._day_requests += 1
            return True

    def record_tokens(self, tokens: int) -> None:
        with self._lock:
            self._roll(self._clock())
            self._day_tokens += max(tokens, 0)


class CircuitBreaker:
    def __init__(
        self, *, failure_threshold: int, open_seconds: float, clock: Clock = time.monotonic
    ) -> None:
        self._threshold = failure_threshold
        self._open_seconds = open_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: deque[float] = deque()
        self._open_until = 0.0
        self._quota_open = _DEFAULT_RATE_LIMIT_OPEN
        self._consecutive_quota = 0

    def allow(self) -> bool:
        with self._lock:
            return self._clock() >= self._open_until

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_quota = 0

    def record_failure(self, reason: FallbackReason, retry_after: float | None = None) -> None:
        with self._lock:
            now = self._clock()
            if reason is FallbackReason.PROVIDER_RATE_LIMITED:
                self._consecutive_quota += 1
                if retry_after is not None:
                    seconds = retry_after
                else:
                    seconds = _DEFAULT_RATE_LIMIT_OPEN * 2 ** (self._consecutive_quota - 1)
                self._open_until = max(self._open_until, now + min(seconds, _MAX_OPEN_SECONDS))
                return
            if reason not in (FallbackReason.PROVIDER_TIMEOUT, FallbackReason.PROVIDER_ERROR):
                return
            self._failures.append(now)
            while self._failures and now - self._failures[0] > _FAILURE_WINDOW:
                self._failures.popleft()
            if len(self._failures) >= self._threshold:
                self._open_until = max(self._open_until, now + self._open_seconds)
                self._failures.clear()
