"""Application settings loaded from environment variables (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
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
    llm_provider: Literal["deterministic", "gemini", "openai_compatible"] = "deterministic"
    gemini_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None  # openai_compatible only (e.g. Groq, OpenRouter)
    llm_api_key: SecretStr | None = None  # openai_compatible only
    llm_timeout_seconds: float = 20.0
    copilot_rate_limit_per_minute: int = 20

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
