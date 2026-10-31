"""HTTP endpoints for the orders module. See docs/architecture/API_CONVENTIONS.md."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.clock import utcnow
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext
from app.domains.orders import queries
from app.domains.orders.models import FulfillmentStatus, OrderStatus, PaymentStatus, SalesChannel
from app.domains.orders.schemas import OrderDetail, OrderListItem, OrderSort

router = APIRouter(prefix="/stores/{store_id}/orders", tags=["orders"])


@router.get("", response_model=Page[OrderListItem])
def list_orders(
    q: str | None = Query(
        None, max_length=64, description="Substring of order number or customer."
    ),
    status: list[OrderStatus] | None = Query(None, description="Repeatable."),
    payment_status: PaymentStatus | None = None,
    fulfillment_status: FulfillmentStatus | None = None,
    channel: SalesChannel | None = None,
    placed_from: AwareDatetime | None = Query(None, description="Inclusive."),
    placed_to: AwareDatetime | None = Query(None, description="Exclusive."),
    overdue: bool | None = Query(
        None, description="BR-202: committed status and ship_by before now (false = the rest)."
    ),
    product_id: uuid.UUID | None = Query(None, description="Orders with a line for this product."),
    sort: OrderSort = "-placed_at",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.ORDERS_READ)),
    db: Session = Depends(get_db),
) -> Page[OrderListItem]:
    filters = queries.OrderFilters(
        q=q,
        statuses=status,
        payment_status=payment_status,
        fulfillment_status=fulfillment_status,
        channel=channel,
        placed_from=placed_from,
        placed_to=placed_to,
        overdue=overdue,
        product_id=product_id,
    )
    return queries.list_orders(
        db, ctx.store_id, filters=filters, sort=sort, paging=paging, as_of=utcnow()
    )


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: uuid.UUID,
    ctx: StoreContext = Depends(require_permission(Permission.ORDERS_READ)),
    db: Session = Depends(get_db),
) -> OrderDetail:
    return queries.get_order(db, ctx.store_id, order_id, as_of=utcnow())
