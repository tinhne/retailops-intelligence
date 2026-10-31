"""Authentication, sessions and store access resolution."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.errors import AuthenticationRequiredError, NotFoundError
from app.domains.audit import service as audit
from app.domains.identity import security
from app.domains.identity.models import Membership, Organization, Store, User, UserSession
from app.domains.identity.permissions import Permission, Role, permissions_for

_LAST_SEEN_GRANULARITY = timedelta(minutes=5)


@dataclass(frozen=True)
class StoreContext:
    """Resolved access context for a store-scoped request."""

    user: User
    store: Store
    role: Role
    permissions: frozenset[Permission]

    @property
    def store_id(self) -> uuid.UUID:
        return self.store.id

    @property
    def organization_id(self) -> uuid.UUID:
        return self.store.organization_id

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


@dataclass(frozen=True)
class OrganizationContext:
    """Resolved access context for an organization-scoped request (members, BR-002)."""

    user: User
    membership: Membership
    permissions: frozenset[Permission]

    @property
    def organization_id(self) -> uuid.UUID:
        return self.membership.organization_id

    @property
    def role(self) -> Role:
        return self.membership.role

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    valid = security.verify_password(user.password_hash if user else None, password)
    if user is None or not valid or not user.is_active:
        audit.record(
            db,
            action="auth.login_failed",
            organization_id=None,
            actor_user_id=user.id if user else None,
            details={"reason": "inactive" if user and valid else "invalid_credentials"},
        )
        db.commit()
        raise AuthenticationRequiredError("Invalid email or password.", code="INVALID_CREDENTIALS")
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    return user


def create_session(
    db: Session,
    user: User,
    *,
    settings: Settings,
    now: datetime,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, UserSession]:
    raw_token, token_hash = security.new_session_token()
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        last_seen_at=now,
        expires_at=now + timedelta(days=settings.session_absolute_days),
        ip=ip,
        user_agent=(user_agent or "")[:300] or None,
    )
    user.last_login_at = now
    db.add(session)
    return raw_token, session


def resolve_session(
    db: Session, raw_token: str, *, settings: Settings, now: datetime
) -> UserSession | None:
    """Return the active session for a cookie token, or None if missing/expired/revoked/idle."""
    session = db.scalar(
        select(UserSession)
        .where(UserSession.token_hash == security.hash_token(raw_token))
        .options(selectinload(UserSession.user))
    )
    if session is None or session.revoked_at is not None or not session.user.is_active:
        return None
    if now >= session.expires_at:
        return None
    if now - session.last_seen_at >= timedelta(hours=settings.session_idle_hours):
        return None
    if now - session.last_seen_at >= _LAST_SEEN_GRANULARITY:
        session.last_seen_at = now
        db.commit()
    return session


def revoke_session(db: Session, session: UserSession, *, now: datetime) -> None:
    session.revoked_at = now


def revoke_user_sessions(db: Session, user_id: uuid.UUID, *, now: datetime) -> int:
    """Revoke every live session of a user (deactivation, ROLE_AND_PERMISSION_WORKFLOW §8.3).

    The next request with any of those cookies gets 401. Returns how many sessions were revoked.
    """
    sessions = db.scalars(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    ).all()
    for session in sessions:
        session.revoked_at = now
    return len(sessions)


def user_names(db: Session, user_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Full names for user ids (no emails), for labelling actors in other modules' views."""
    ids = set(user_ids)
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    return {user_id: full_name for user_id, full_name in rows}


def memberships_for(db: Session, user_id: uuid.UUID) -> list[Membership]:
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .options(selectinload(Membership.organization).selectinload(Organization.stores))
        .order_by(Membership.created_at)
    )
    return list(db.scalars(stmt).all())


def store_context(db: Session, user: User, store_id: uuid.UUID) -> StoreContext:
    """Resolve the caller's role for a store.

    A store outside the caller's organizations is reported as 404, not 403, so its existence is
    not revealed (BR-003).
    """
    row = db.execute(
        select(Store, Membership.role)
        .join(Membership, Membership.organization_id == Store.organization_id)
        .where(Store.id == store_id, Membership.user_id == user.id)
    ).first()
    if row is None:
        raise NotFoundError("Store not found.")
    store, role = row
    return StoreContext(user=user, store=store, role=role, permissions=permissions_for(role))


def organization_context(
    db: Session, user: User, organization_id: uuid.UUID
) -> OrganizationContext:
    """Resolve the caller's membership in an organization.

    An organization the caller does not belong to is reported as 404, not 403 (BR-003).
    """
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id, Membership.user_id == user.id
        )
    )
    if membership is None:
        raise NotFoundError("Organization not found.")
    return OrganizationContext(
        user=user, membership=membership, permissions=permissions_for(membership.role)
    )
