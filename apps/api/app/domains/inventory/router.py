"""HTTP endpoints for the inventory module. See docs/architecture/API_CONVENTIONS.md."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.clock import utcnow
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.identity import store_service
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext
from app.domains.inventory import queries
from app.domains.inventory.calculations import StockHealth
from app.domains.inventory.models import MovementSource, MovementType
from app.domains.inventory.schemas import (
    InventoryPositionOut,
    MovementOut,
    MovementSort,
    PositionSort,
    ReconciliationOut,
)

router = APIRouter(prefix="/stores/{store_id}/inventory", tags=["inventory"])


@router.get("/positions", response_model=Page[InventoryPositionOut])
def list_positions(
    q: str | None = Query(None, max_length=100, description="Substring of SKU or name."),
    health: list[StockHealth] | None = Query(None, description="Repeatable."),
    category: str | None = Query(None, max_length=100),
    include_inactive: bool = Query(False, description="Include DRAFT and ARCHIVED products."),
    sort: PositionSort = "available",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.INVENTORY_READ)),
    db: Session = Depends(get_db),
) -> Page[InventoryPositionOut]:
    settings = store_service.get_settings(db, ctx.store_id)
    return queries.list_positions(
        db,
        ctx.store_id,
        q=q,
        health=health,
        category=category,
        include_inactive=include_inactive,
        sort=sort,
        paging=paging,
        as_of=utcnow(),
        factor=settings.approaching_reorder_factor,
        window_days=settings.velocity_window_days,
    )


@router.get("/movements", response_model=Page[MovementOut])
def list_movements(
    product_id: uuid.UUID | None = None,
    movement_type: list[MovementType] | None = Query(None, description="Repeatable."),
    source: MovementSource | None = None,
    occurred_from: AwareDatetime | None = Query(None, alias="from", description="Inclusive."),
    occurred_to: AwareDatetime | None = Query(None, alias="to", description="Exclusive."),
    sort: MovementSort = "-recorded_at",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.INVENTORY_READ)),
    db: Session = Depends(get_db),
) -> Page[MovementOut]:
    return queries.list_movements(
        db,
        ctx.store_id,
        product_id=product_id,
        movement_types=movement_type,
        source=source,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        sort=sort,
        paging=paging,
    )


@router.get("/reconciliation", response_model=ReconciliationOut)
def get_reconciliation(
    ctx: StoreContext = Depends(require_permission(Permission.INVENTORY_READ)),
    db: Session = Depends(get_db),
) -> ReconciliationOut:
    return queries.reconciliation(db, ctx.store_id, checked_at=utcnow())
