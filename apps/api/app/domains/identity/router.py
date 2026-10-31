"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    Principal,
    get_principal,
    login_limiter,
)
from app.core.clock import utcnow
from app.core.config import Settings, get_settings
from app.core.context import current_client_ip
from app.core.errors import NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.domains.audit import service as audit
from app.domains.identity import service as identity
from app.domains.identity.models import User, UserSession
from app.domains.identity.permissions import ROLE_PERMISSIONS, Role, permissions_for
from app.domains.identity.schemas import (
    LoginRequest,
    MembershipOut,
    MeResponse,
    RolePermissionsOut,
    StoreSummary,
    UserOut,
)
from app.domains.identity.security import csrf_token_for

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(db: Session, user: User, session: UserSession, settings: Settings) -> MeResponse:
    memberships = [
        MembershipOut(
            organization_id=m.organization_id,
            organization_name=m.organization.name,
            is_demo=m.organization.is_demo,
            role=m.role.value,
            permissions=sorted(p.value for p in permissions_for(m.role)),
            stores=[
                StoreSummary(
                    id=s.id, name=s.name, code=s.code, currency=s.currency, timezone=s.timezone
                )
                for s in sorted(m.organization.stores, key=lambda s: s.name)
            ],
        )
        for m in identity.memberships_for(db, user.id)
    ]
    return MeResponse(
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name),
        memberships=memberships,
        csrf_token=csrf_token_for(session.token_hash, settings.session_secret.get_secret_value()),
    )


def _set_session_cookies(
    response: Response, raw_token: str, csrf_token: str, settings: Settings
) -> None:
    max_age = settings.session_absolute_days * 24 * 3600
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _start_session(
    db: Session,
    request: Request,
    response: Response,
    user: User,
    settings: Settings,
    action: str,
) -> MeResponse:
    raw_token, session = identity.create_session(
        db,
        user,
        settings=settings,
        now=utcnow(),
        ip=current_client_ip(),
        user_agent=request.headers.get("user-agent"),
    )
    memberships = identity.memberships_for(db, user.id)
    audit.record(
        db,
        action=action,
        organization_id=memberships[0].organization_id if memberships else None,
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    me = _me(db, user, session, settings)
    _set_session_cookies(response, raw_token, me.csrf_token, settings)
    return me


@router.post("/login", response_model=MeResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    email = identity.normalize_email(body.email)
    login_limiter(request).hit(f"login:{current_client_ip()}:{email}")
    user = identity.authenticate(db, email, body.password)
    return _start_session(db, request, response, user, settings, "auth.login")


@router.post("/demo", response_model=MeResponse)
def demo_login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    """Sign in as the read-only public demo viewer (ADR-0011)."""
    if not settings.demo_mode_enabled:
        raise NotFoundError("Demo mode is not enabled.")
    login_limiter(request).hit(f"demo:{current_client_ip()}")
    user = db.scalar(select(User).where(User.email == settings.demo_user_email))
    if user is None or not user.is_active:
        raise NotFoundError("The demo is not available right now.", code="DEMO_UNAVAILABLE")
    memberships = identity.memberships_for(db, user.id)
    # Safety net: the shared demo account must never hold a mutating role.
    if not memberships or any(m.role is not Role.VIEWER for m in memberships):
        raise PermissionDeniedError("Demo account is misconfigured.", code="DEMO_MISCONFIGURED")
    return _start_session(db, request, response, user, settings, "auth.demo_login")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Response:
    identity.revoke_session(db, principal.session, now=utcnow())
    memberships = identity.memberships_for(db, principal.user.id)
    audit.record(
        db,
        action="auth.logout",
        organization_id=memberships[0].organization_id if memberships else None,
        actor_user_id=principal.user.id,
        target_type="user",
        target_id=principal.user.id,
    )
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response


@router.get("/me", response_model=MeResponse)
def me(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    return _me(db, principal.user, principal.session, settings)


roles_router = APIRouter(tags=["auth"])


@roles_router.get("/roles", response_model=list[RolePermissionsOut])
def list_roles(_: Principal = Depends(get_principal)) -> list[RolePermissionsOut]:
    """The code-defined role → permission matrix (ADR-0007), for read-only display in the UI."""
    return [
        RolePermissionsOut(role=role.value, permissions=sorted(p.value for p in perms))
        for role, perms in ROLE_PERMISSIONS.items()
    ]
