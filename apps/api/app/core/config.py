"""Application settings loaded from environment variables (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEV_SECRET = "dev-only-insecure-session-secret"  # noqa: S105 - local default only


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str = "postgresql+psycopg://retailops:retailops@localhost:54329/retailops"
    log_level: str = "INFO"
    trust_proxy_headers: bool = False

    session_secret: SecretStr = SecretStr(_INSECURE_DEV_SECRET)
    cookie_secure: bool = False
    session_idle_hours: int = 12
    session_absolute_days: int = 7

    login_rate_limit_per_minute: int = 5
    api_rate_limit_per_minute: int = 300

    demo_mode_enabled: bool = True
    demo_user_email: str = "demo@kestrel.example"

    # Free-tier providers only (ADR-0010). "deterministic" needs no key and is the fallback.
    # Unset: "gemini" when GEMINI_API_KEY is set, otherwise "deterministic" (AI_ARCHITECTURE §8.1).
    llm_provider: Literal["deterministic", "gemini", "openai_compatible"] | None = None
    gemini_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None  # openai_compatible only (e.g. Groq, OpenRouter)
    llm_api_key: SecretStr | None = None  # openai_compatible only
    llm_timeout_seconds: float = 20.0  # one live LLM request
    copilot_rate_limit_per_minute: int = 20

    # Per-instance guard below the provider's free-tier quota (AI_ARCHITECTURE §4.2).
    llm_budget_requests_per_minute: int = 10
    llm_budget_requests_per_day: int = 500
    llm_budget_tokens_per_day: int = 1_000_000

    # Copilot turn limits (AI_ARCHITECTURE §4.2, §10).
    ai_turn_deadline_seconds: float = 45.0
    ai_max_tool_iterations: int = 6
    ai_max_tool_calls_per_turn: int = 12
    ai_tool_timeout_seconds: float = 5.0
    ai_tool_max_rows: int = 50
    ai_tool_max_result_bytes: int = 16_384
    ai_max_input_tokens_per_turn: int = 30_000
    ai_max_output_tokens: int = 4_096
    ai_history_turns: int = 4
    ai_max_messages_per_conversation: int = 50
    ai_summary_cache_ttl_hours: int = 12
    ai_circuit_failure_threshold: int = 5
    ai_circuit_open_seconds: float = 60.0

    @field_validator(
        "llm_provider", "gemini_api_key", "llm_model", "llm_base_url", "llm_api_key", mode="before"
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # `.env.example` lists these with empty values; an empty value means "not configured".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.app_env == "production":
            if self.session_secret.get_secret_value() == _INSECURE_DEV_SECRET:
                raise ValueError("SESSION_SECRET must be set in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
