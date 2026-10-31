"""HTTP endpoints for the analytics module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.clock import utcnow
from app.db.session import get_db
from app.domains.analytics import service
from app.domains.analytics.schemas import DashboardOut, ExceptionBreakdownOut, TrendsOut
from app.domains.identity import store_service
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext

router = APIRouter(prefix="/stores/{store_id}/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    ctx: StoreContext = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: Session = Depends(get_db),
) -> DashboardOut:
    settings = store_service.get_settings(db, ctx.store_id)
    return service.get_dashboard_summary(
        db,
        ctx.store_id,
        timezone=ctx.store.timezone,
        currency=ctx.store.currency,
        approaching_factor=settings.approaching_reorder_factor,
        as_of=utcnow(),
    )


@router.get("/trends", response_model=TrendsOut)
def get_trends(
    days: int = Query(30, ge=7, le=90, description="Store-local days, ending today."),
    ctx: StoreContext = Depends(require_permission(Permission.ANALYTICS_READ)),
    db: Session = Depends(get_db),
) -> TrendsOut:
    return service.get_trends(
        db,
        ctx.store_id,
        timezone=ctx.store.timezone,
        currency=ctx.store.currency,
        days=days,
        as_of=utcnow(),
    )


@router.get("/exceptions-breakdown", response_model=ExceptionBreakdownOut)
def get_exception_breakdown(
    days: int = Query(30, ge=1, le=90, description="Store-local days, ending today."),
    ctx: StoreContext = Depends(require_permission(Permission.ANALYTICS_READ)),
    db: Session = Depends(get_db),
) -> ExceptionBreakdownOut:
    return service.get_exception_breakdown(
        db, ctx.store_id, timezone=ctx.store.timezone, days=days, as_of=utcnow()
    )
