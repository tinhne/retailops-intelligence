"""Store details and operational settings endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.domains.analytics import service as analytics
from app.domains.identity import store_service
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext
from app.domains.identity.store_schemas import (
    MemberList,
    StoreDetailOut,
    StoreSettingsOut,
    StoreSettingsUpdate,
)

router = APIRouter(prefix="/stores/{store_id}", tags=["stores"])


@router.get("", response_model=StoreDetailOut)
def get_store(
    ctx: StoreContext = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: Session = Depends(get_db),
) -> StoreDetailOut:
    """Store details, operational settings and data freshness (latest import per type and the
    latest evaluation run)."""
    return StoreDetailOut(
        store=store_service.get_store(ctx),
        settings=store_service.get_settings(db, ctx.store_id),
        data_freshness=analytics.data_freshness(db, ctx.store_id),
    )


@router.get("/settings", response_model=StoreSettingsOut)
def get_settings(
    ctx: StoreContext = Depends(require_permission(Permission.SETTINGS_READ)),
    db: Session = Depends(get_db),
) -> StoreSettingsOut:
    return store_service.get_settings(db, ctx.store_id)


@router.patch("/settings", response_model=StoreSettingsOut)
def update_settings(
    body: StoreSettingsUpdate,
    ctx: StoreContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
) -> StoreSettingsOut:
    """Partial update of the thresholds in BUSINESS_RULES.md §7, audited as ``settings.update``."""
    return store_service.update_settings(db, ctx, body)


@router.get("/members", response_model=MemberList)
def list_members(
    ctx: StoreContext = Depends(require_permission(Permission.EXCEPTIONS_READ)),
    db: Session = Depends(get_db),
) -> MemberList:
    """Organization members for the assignee picker: name, role and whether they can work
    exceptions. Emails are not exposed."""
    return store_service.list_members(db, ctx.organization_id)
