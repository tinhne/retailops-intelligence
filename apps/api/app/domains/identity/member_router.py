"""Organization member endpoints (API_CONVENTIONS.md §12.1, ROLE_AND_PERMISSION_WORKFLOW.md §8)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_org_permission
from app.core.clock import utcnow
from app.db.session import get_db
from app.domains.identity import member_service
from app.domains.identity.member_schemas import (
    MemberCreate,
    MemberCreated,
    MemberUpdate,
    OrganizationMemberList,
    OrganizationMemberOut,
)
from app.domains.identity.permissions import Permission
from app.domains.identity.service import OrganizationContext

router = APIRouter(prefix="/organizations/{organization_id}/members", tags=["members"])


@router.get("", response_model=OrganizationMemberList)
def list_members(
    ctx: OrganizationContext = Depends(require_org_permission(Permission.USERS_READ)),
    db: Session = Depends(get_db),
) -> OrganizationMemberList:
    """Members with email, role and status. Organizations are small, so there is no paging."""
    return member_service.list_members(db, ctx)


@router.post("", response_model=MemberCreated, status_code=status.HTTP_201_CREATED)
def add_member(
    body: MemberCreate,
    ctx: OrganizationContext = Depends(require_org_permission(Permission.USERS_MANAGE)),
    db: Session = Depends(get_db),
) -> MemberCreated:
    """Create an account with a temporary password shown once, audited as ``user.create``.

    ``409 MEMBER_EXISTS`` when the email is already a member here, ``409 EMAIL_IN_USE`` when it
    has an account in another organization (not supported in v1, open question O-35).
    """
    return member_service.add_member(db, ctx, body)


@router.patch("/{membership_id}", response_model=OrganizationMemberOut)
def update_member(
    membership_id: uuid.UUID,
    body: MemberUpdate,
    ctx: OrganizationContext = Depends(require_org_permission(Permission.USERS_MANAGE)),
    db: Session = Depends(get_db),
) -> OrganizationMemberOut:
    """Change the role and/or status. ``409 LAST_OWNER`` keeps one active owner; deactivation
    revokes every session of the member. Members cannot change their own membership (403)."""
    return member_service.update_member(db, ctx, membership_id, body, now=utcnow())
