"""FastAPI application factory."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db import models  # noqa: F401  (registers all tables on the metadata)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="RetailOps Intelligence API",
        version="0.1.0",
        description="E-commerce operations and decision intelligence.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.login_limiter = SlidingWindowRateLimiter(settings.login_rate_limit_per_minute, 60)
    app.state.api_limiter = SlidingWindowRateLimiter(settings.api_rate_limit_per_minute, 60)

    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware, trust_proxy_headers=settings.trust_proxy_headers)
    app.include_router(api_router)
    return app


app = create_app()
