"""Request dependencies: authentication, CSRF, rate limiting and permission checks."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationRequiredError, PermissionDeniedError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.session import get_db
from app.domains.identity import service as identity
from app.domains.identity.models import User, UserSession
from app.domains.identity.permissions import Permission
from app.domains.identity.security import csrf_matches, csrf_token_for

SESSION_COOKIE = "ro_session"
CSRF_COOKIE = "ro_csrf"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class Principal:
    user: User
    session: UserSession


def api_limiter(request: Request) -> SlidingWindowRateLimiter:
    limiter: SlidingWindowRateLimiter = request.app.state.api_limiter
    return limiter


def login_limiter(request: Request) -> SlidingWindowRateLimiter:
    limiter: SlidingWindowRateLimiter = request.app.state.login_limiter
    return limiter


def require_pre_session_csrf(request: Request) -> None:
    """Double-submit check for the sign-in endpoints, which run before a session exists.

    The ``X-CSRF-Token`` header must equal the ``ro_csrf`` cookie issued by ``GET /auth/csrf``
    (ADR-0004). A cross-site page can neither read that cookie nor send a custom header without
    a CORS preflight, which the API never grants, so login CSRF is blocked.
    """
    cookie = request.cookies.get(CSRF_COOKIE)
    if not cookie or not csrf_matches(cookie, request.headers.get(CSRF_HEADER)):
        raise PermissionDeniedError("Missing or invalid CSRF token.", code="CSRF_FAILED")


def get_principal(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Principal:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AuthenticationRequiredError("Authentication required.")
    session = identity.resolve_session(db, token, settings=settings, now=utcnow())
    if session is None:
        raise AuthenticationRequiredError(
            "Your session has expired. Please sign in again.", code="SESSION_EXPIRED"
        )
    if request.method not in _SAFE_METHODS:
        expected = csrf_token_for(session.token_hash, settings.session_secret.get_secret_value())
        if not csrf_matches(expected, request.headers.get(CSRF_HEADER)):
            raise PermissionDeniedError("Missing or invalid CSRF token.", code="CSRF_FAILED")
    api_limiter(request).hit(f"user:{session.user_id}")
    return Principal(user=session.user, session=session)


def require_permission(*required: Permission) -> Callable[..., identity.StoreContext]:
    """Dependency factory for store-scoped routes (path parameter ``store_id``).

    Resolves the caller's membership for the store's organization (404 if none) and checks that
    the role grants every required permission (403 otherwise).
    """

    def dependency(
        store_id: uuid.UUID,
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> identity.StoreContext:
        ctx = identity.store_context(db, principal.user, store_id)
        missing = [p.value for p in required if p not in ctx.permissions]
        if missing:
            raise PermissionDeniedError(
                "Your role does not allow this action.",
                details=[{"missing_permission": p} for p in missing],
            )
        return ctx

    return dependency
