"""Process-wide copilot state: provider selection, the LLM budget, circuit breakers, the copilot
rate limiter and the shared HTTP client (AI_ARCHITECTURE.md §8.1).

One ``CopilotRuntime`` lives on ``app.state`` per API process. Tests and the evaluation harness
build their own with a fake provider factory, a fixed clock or a blocking HTTP transport.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import httpx

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.domains.ai.budget import CircuitBreaker, LLMBudget
from app.domains.ai.ledger import EvidenceLedger
from app.domains.ai.models import FallbackReason
from app.domains.ai.providers.base import LLMProvider
from app.domains.ai.providers.gemini import GeminiProvider
from app.domains.ai.providers.openai_compatible import OpenAICompatibleProvider

LiveProviderName = Literal["gemini", "openai_compatible"]
ProviderFactory = Callable[[Settings, httpx.Client], LLMProvider | None]
CandidateHook = Callable[[str, Any, EvidenceLedger], None]  # provider, raw candidate, ledger


def configured_provider(
    settings: Settings,
) -> Literal["deterministic", "gemini", "openai_compatible"]:
    """§8.1: unset → gemini when GEMINI_API_KEY is set, otherwise deterministic."""
    if settings.llm_provider is not None:
        return settings.llm_provider
    return "gemini" if settings.gemini_api_key is not None else "deterministic"


def default_provider_factory(settings: Settings, client: httpx.Client) -> LLMProvider | None:
    """The configured live adapter, or None when its settings are incomplete."""
    name = configured_provider(settings)
    if name == "gemini" and settings.gemini_api_key is not None:
        return GeminiProvider(
            client, api_key=settings.gemini_api_key.get_secret_value(), model=settings.llm_model
        )
    if (
        name == "openai_compatible"
        and settings.llm_base_url
        and settings.llm_api_key is not None
        and settings.llm_model
    ):
        return OpenAICompatibleProvider(
            client,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
        )
    return None


@dataclass
class CopilotRuntime:
    settings: Settings
    provider_factory: ProviderFactory = default_provider_factory
    clock: Callable[[], datetime] = utcnow
    http_client: httpx.Client | None = None
    candidate_hook: CandidateHook | None = None  # evaluation harness only: raw candidates
    budget: LLMBudget = field(init=False)
    limiter: SlidingWindowRateLimiter = field(init=False)
    _circuits: dict[str, CircuitBreaker] = field(init=False, default_factory=dict)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)

    def __post_init__(self) -> None:
        s = self.settings
        self.budget = LLMBudget(
            requests_per_minute=s.llm_budget_requests_per_minute,
            requests_per_day=s.llm_budget_requests_per_day,
            tokens_per_day=s.llm_budget_tokens_per_day,
        )
        self.limiter = SlidingWindowRateLimiter(s.copilot_rate_limit_per_minute, 60)
        if self.http_client is None:
            self.http_client = httpx.Client(follow_redirects=False)

    @property
    def configured(self) -> str:
        return configured_provider(self.settings)

    @property
    def mode(self) -> Literal["llm", "deterministic"]:
        return "deterministic" if self.configured == "deterministic" else "llm"

    def circuit(self, name: str) -> CircuitBreaker:
        with self._lock:
            if name not in self._circuits:
                self._circuits[name] = CircuitBreaker(
                    failure_threshold=self.settings.ai_circuit_failure_threshold,
                    open_seconds=self.settings.ai_circuit_open_seconds,
                )
            return self._circuits[name]

    def configured_live(self) -> LLMProvider | None:
        """The configured live adapter whatever its circuit state (summary cache keys)."""
        if self.configured == "deterministic":
            return None
        assert self.http_client is not None
        return self.provider_factory(self.settings, self.http_client)

    def live_provider(self) -> tuple[LLMProvider | None, FallbackReason | None]:
        """The live adapter to try for this turn, or why there is none.

        ``(None, None)`` means deterministic is the configured mode: no fallback notice.
        """
        if self.configured == "deterministic":
            return None, None
        assert self.http_client is not None
        provider = self.provider_factory(self.settings, self.http_client)
        if provider is None:
            return None, FallbackReason.PROVIDER_NOT_CONFIGURED
        if not self.circuit(provider.name).allow():
            return None, FallbackReason.CIRCUIT_OPEN
        return provider, None


_RUNTIME_LOCK = threading.Lock()


def runtime_for(state: Any, settings: Settings) -> CopilotRuntime:
    """The process runtime stored on ``app.state`` (created on first use)."""
    runtime: CopilotRuntime | None = getattr(state, "copilot", None)
    if runtime is None:
        with _RUNTIME_LOCK:
            runtime = getattr(state, "copilot", None)
            if runtime is None:
                runtime = CopilotRuntime(settings)
                state.copilot = runtime
    return runtime
