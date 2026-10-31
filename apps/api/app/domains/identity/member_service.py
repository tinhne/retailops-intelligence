"""Organization member administration (ROLE_AND_PERMISSION_WORKFLOW.md §8).

v1 has no email delivery: an owner adds a member by creating their account with a random
temporary password that is shown once (§8.1). Deactivation sets ``app_user.is_active = false``
and revokes every session of the user (§8.3). Roles stay code-defined (ADR-0007): only the
membership's role changes, never what a role grants.
"""

import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.domains.audit import service as audit
from app.domains.identity import security
from app.domains.identity.member_schemas import (
    MemberCreate,
    MemberCreated,
    MemberStatus,
    MemberUpdate,
    OrganizationMemberList,
    OrganizationMemberOut,
)
from app.domains.identity.models import Membership, Organization, User
from app.domains.identity.permissions import Role
from app.domains.identity.service import (
    OrganizationContext,
    normalize_email,
    revoke_user_sessions,
)

# 12 random bytes → 16 URL-safe characters (96 bits of entropy).
TEMPORARY_PASSWORD_BYTES = 12


def _to_out(membership: Membership, user: User) -> OrganizationMemberOut:
    return OrganizationMemberOut(
        id=membership.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=membership.role,
        status=MemberStatus.ACTIVE if user.is_active else MemberStatus.DEACTIVATED,
        joined_at=membership.created_at,
        last_login_at=user.last_login_at,
    )


def list_members(db: Session, ctx: OrganizationContext) -> OrganizationMemberList:
    """Every member of the organization, active or not, sorted by name."""
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == ctx.organization_id)
        .order_by(func.lower(User.full_name), User.id)
    ).all()
    return OrganizationMemberList(items=[_to_out(m, u) for m, u in rows])


def _record(
    db: Session,
    ctx: OrganizationContext,
    action: str,
    user: User,
    membership: Membership,
    details: dict[str, Any] | None = None,
) -> None:
    """Organization-level audit row (no store). Never contains passwords or tokens."""
    audit.record(
        db,
        action=action,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        target_type="user",
        target_id=user.id,
        details={
            "membership_id": str(membership.id),
            "full_name": user.full_name,
            **(details or {}),
        },
    )


def add_member(db: Session, ctx: OrganizationContext, body: MemberCreate) -> MemberCreated:
    """Create the account and its membership, returning the temporary password once (§8.1).

    An email that already has an account is refused (open question O-35: attaching an existing
    account to another organization is not supported in v1).
    """
    email = normalize_email(body.email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        already_member = db.scalar(
            select(Membership.id).where(
                Membership.user_id == existing.id,
                Membership.organization_id == ctx.organization_id,
            )
        )
        if already_member is not None:
            raise ConflictError(
                "This person is already a member of the organization.", code="MEMBER_EXISTS"
            )
        raise ConflictError(
            "An account with this email already exists. Adding an existing account to another "
            "organization is not supported yet.",
            code="EMAIL_IN_USE",
        )

    temporary_password = secrets.token_urlsafe(TEMPORARY_PASSWORD_BYTES)
    user = User(
        email=email,
        full_name=body.full_name,
        password_hash=security.hash_password(temporary_password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # a concurrent request created the same email
        db.rollback()
        raise ConflictError(
            "An account with this email already exists.", code="EMAIL_IN_USE"
        ) from None
    membership = Membership(user_id=user.id, organization_id=ctx.organization_id, role=body.role)
    db.add(membership)
    db.flush()
    _record(db, ctx, "user.create", user, membership, {"role": body.role.value})
    db.commit()
    db.refresh(membership)
    db.refresh(user)
    return MemberCreated(member=_to_out(membership, user), temporary_password=temporary_password)


def _active_owner_count(db: Session, organization_id: uuid.UUID, *, excluding: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == Role.OWNER,
                User.is_active.is_(True),
                Membership.id != excluding,
            )
        )
        or 0
    )


def update_member(
    db: Session,
    ctx: OrganizationContext,
    membership_id: uuid.UUID,
    changes: MemberUpdate,
    *,
    now: datetime,
) -> OrganizationMemberOut:
    """Change a member's role and/or status (§8.2, §8.3).

    Checks in API order: 404 (not a member of this organization) → 409 (``LAST_OWNER``, or an
    account shared with another organization) → 403 (changing your own membership). A request
    that changes nothing returns the member unchanged and writes no audit row.
    """
    # Serialise member administration per organization, so two owners demoting each other at
    # the same time cannot leave it without an owner.
    db.execute(
        select(Organization.id).where(Organization.id == ctx.organization_id).with_for_update()
    )
    row = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.id == membership_id, Membership.organization_id == ctx.organization_id)
        .with_for_update()
    ).first()
    if row is None:
        raise NotFoundError("Member not found.")
    membership, user = row

    new_role = changes.role if changes.role is not None else membership.role
    new_active = (
        changes.status is MemberStatus.ACTIVE if changes.status is not None else user.is_active
    )
    role_changes = new_role is not membership.role
    status_changes = new_active != user.is_active
    if not role_changes and not status_changes:
        db.rollback()  # release the locks
        return _to_out(membership, user)

    stops_being_owner = (
        membership.role is Role.OWNER
        and user.is_active
        and (new_role is not Role.OWNER or not new_active)
    )
    other_owners = (
        _active_owner_count(db, ctx.organization_id, excluding=membership.id)
        if stops_being_owner
        else None
    )
    if other_owners == 0:
        raise ConflictError(
            "At least one owner is required. Make another member an owner first.",
            code="LAST_OWNER",
        )
    if status_changes:
        # The account status is stored on the user, so it would also apply to other organizations.
        other_orgs = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.user_id == user.id,
                Membership.organization_id != ctx.organization_id,
            )
        )
        if other_orgs:
            raise ConflictError(
                "This person also belongs to another organization, so their account can't be "
                "deactivated or reactivated from here.",
                code="MEMBER_IN_OTHER_ORGANIZATION",
            )
    if user.id == ctx.user.id:
        raise PermissionDeniedError(
            "You can't change your own role or deactivate yourself. Ask another owner.",
            code="OWN_MEMBERSHIP",
        )

    if role_changes:
        from_role = membership.role
        membership.role = new_role
        _record(
            db,
            ctx,
            "user.role_change",
            user,
            membership,
            {"from_role": from_role.value, "to_role": new_role.value},
        )
    if status_changes:
        user.is_active = new_active
        if new_active:
            _record(db, ctx, "user.reactivate", user, membership)
        else:
            revoked = revoke_user_sessions(db, user.id, now=now)
            _record(db, ctx, "user.deactivate", user, membership, {"sessions_revoked": revoked})
            if revoked:
                _record(
                    db,
                    ctx,
                    "auth.session_revoked",
                    user,
                    membership,
                    {"cause": "user.deactivate", "sessions_revoked": revoked},
                )
    db.commit()
    return _to_out(membership, user)
