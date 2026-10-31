"""Product and inventory tools: get_product, get_inventory_position, get_inventory_movements
(TOOL_CATALOG.md §2.6–2.8).

Stock, health and the labelled estimates come from ``catalog.queries.get_product`` and the ledger
from ``inventory.queries.list_movements``, the functions behind the REST endpoints. ``unit_cost``
and supplier contact references are never returned.
"""

import uuid
from datetime import timedelta
from typing import Any

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import PageParams
from app.domains.ai.tools.base import (
    ToolArgs,
    ToolContext,
    ToolOutput,
    ToolSpec,
    check_since,
    not_found,
    ref,
)
from app.domains.ai.tools.order_tools import active_exception_refs
from app.domains.ai.tools.sanitize import MOVEMENT_NOTE_MAX, NAME_MAX, REFERENCE_MAX, TextGuard
from app.domains.catalog import queries as catalog
from app.domains.catalog.models import Product
from app.domains.catalog.schemas import ProductDetail
from app.domains.exceptions.models import EntityType
from app.domains.identity import store_service
from app.domains.identity.permissions import Permission
from app.domains.inventory import queries as inventory
from app.domains.inventory.models import MovementType
from app.domains.orders import queries as orders
from app.domains.orders.models import Order, OrderItem
from app.domains.orders.state import PENDING_DEMAND_STATUSES

SEARCH_CAP = 10
MOVEMENTS_DEFAULT_DAYS = 30
FORMULAS = {
    "available": "available = on_hand − reserved (BR-101); incoming is not included (BR-103)",
    "pending_demand": "pending_demand = Σ units on CREATED / PAYMENT_PENDING orders",
    "potential_shortage": "potential_shortage = pending_demand − available when available ≥ 0, "
    "else 0 (BR-403)",
    "avg_daily_units": "avg_daily_units = units sold in the velocity window ÷ window days "
    "(BR-150, estimate)",
    "days_of_cover": "days_of_cover = max(available, 0) ÷ avg_daily_units (BR-151, estimate)",
}


class ProductSelector(ToolArgs):
    product_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, min_length=1, max_length=64)


def _resolve_product(db: Session, ctx: ToolContext, args: ProductSelector) -> uuid.UUID:
    condition = (
        Product.sku == args.sku.strip() if args.sku is not None else Product.id == args.product_id
    )
    product_id = db.scalar(select(Product.id).where(Product.store_id == ctx.store_id, condition))
    if product_id is None:
        raise not_found("product")
    return product_id


def _detail(db: Session, ctx: ToolContext, product_id: uuid.UUID) -> ProductDetail:
    settings = store_service.get_settings(db, ctx.store_id)
    try:
        return catalog.get_product(
            db,
            ctx.store_id,
            product_id,
            as_of=ctx.as_of,
            factor=settings.approaching_reorder_factor,
            window_days=settings.velocity_window_days,
        )
    except NotFoundError as err:
        raise not_found("product") from err


def product_label(sku: str, name: str, guard: TextGuard) -> str:
    return f"{sku} · {guard(name, NAME_MAX)}"


def _one_selector(values: list[object]) -> None:
    if sum(v is not None for v in values) != 1:
        raise ValueError("exactly one selector is required")


# --- get_product ---------------------------------------------------------------------------------


class GetProductArgs(ToolArgs):
    product_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    search: str | None = Field(default=None, min_length=2, max_length=100)

    @model_validator(mode="after")
    def _selector(self) -> "GetProductArgs":
        _one_selector([self.product_id, self.sku, self.search])
        return self


def get_product(db: Session, ctx: ToolContext, args: GetProductArgs) -> ToolOutput:
    untrusted = [
        "records[].ref.label",
        "records[].name",
        "records[].category",
        "records[].supplier.name",
    ]
    if args.search is not None:
        settings = store_service.get_settings(db, ctx.store_id)
        page = catalog.list_products(
            db,
            ctx.store_id,
            q=args.search.strip(),
            status=None,
            category=None,
            supplier_id=None,
            health=None,
            sort="sku",
            paging=PageParams(page=1, page_size=SEARCH_CAP),
            factor=settings.approaching_reorder_factor,
        )
        records = []
        for item in page.items:
            guard = TextGuard()
            linked = orders.linked_exceptions(db, ctx.store_id, EntityType.PRODUCT, item.id)
            records.append(
                guard.mark(
                    {
                        "ref": ref("product", item.id, product_label(item.sku, item.name, guard)),
                        "sku": item.sku,
                        "name": guard(item.name, NAME_MAX),
                        "category": guard(item.category, NAME_MAX),
                        "status": item.status,
                        "unit_price": item.unit_price,
                        "reorder_point": item.reorder_point,
                        "reorder_quantity": item.reorder_quantity,
                        "supplier": {"name": guard(item.supplier.name, NAME_MAX)}
                        if item.supplier
                        else None,
                        "available": item.available,
                        "health": item.health,
                        "updated_at": item.updated_at,
                        "active_exceptions": active_exception_refs(linked, guard),
                    }
                )
            )
        return ToolOutput(records=records, total_available=page.total, untrusted_fields=untrusted)

    product_id = _resolve_product(
        db, ctx, ProductSelector(product_id=args.product_id, sku=args.sku)
    )
    detail = _detail(db, ctx, product_id)
    guard = TextGuard()
    linked = orders.linked_exceptions(db, ctx.store_id, EntityType.PRODUCT, product_id)
    record = {
        "ref": ref("product", detail.id, product_label(detail.sku, detail.name, guard)),
        "sku": detail.sku,
        "name": guard(detail.name, NAME_MAX),
        "category": guard(detail.category, NAME_MAX),
        "status": detail.status,
        "unit_price": detail.unit_price,
        "reorder_point": detail.reorder_point,
        "reorder_quantity": detail.reorder_quantity,
        "supplier": (
            {
                "name": guard(detail.supplier.name, NAME_MAX),
                "lead_time_days": detail.supplier.lead_time_days,
            }
            if detail.supplier
            else None
        ),
        "updated_at": detail.updated_at,
        "active_exceptions": active_exception_refs(linked, guard),
    }
    return ToolOutput(records=[guard.mark(record)], untrusted_fields=untrusted)


# --- get_inventory_position ----------------------------------------------------------------------


class GetInventoryPositionArgs(ProductSelector):
    @model_validator(mode="after")
    def _selector(self) -> "GetInventoryPositionArgs":
        _one_selector([self.product_id, self.sku])
        return self


def _pending_demand(db: Session, ctx: ToolContext, product_id: uuid.UUID) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.store_id == ctx.store_id,
            Order.store_id == ctx.store_id,
            OrderItem.product_id == product_id,
            Order.status.in_(PENDING_DEMAND_STATUSES),
        )
    )
    return int(total or 0)


def get_inventory_position(
    db: Session, ctx: ToolContext, args: GetInventoryPositionArgs
) -> ToolOutput:
    product_id = _resolve_product(db, ctx, args)
    detail = _detail(db, ctx, product_id)
    guard = TextGuard()
    stock = detail.stock
    pending = _pending_demand(db, ctx, product_id)
    shortage = max(pending - stock.available, 0) if stock.available >= 0 else 0
    velocity = detail.avg_daily_units
    cover = detail.days_of_cover
    record: dict[str, Any] = {
        "ref": ref("product", detail.id, product_label(detail.sku, detail.name, guard)),
        "status": detail.status,
        "on_hand": stock.on_hand,
        "reserved": stock.reserved,
        "available": stock.available,
        "incoming": stock.incoming,
        "incoming_eta": stock.incoming_eta,
        "pending_demand": pending,
        "potential_shortage": shortage,
        "health": detail.health.value if detail.health else "NOT_CLASSIFIED",
        "reorder_point": detail.reorder_point,
        "approaching_threshold": detail.approaching_threshold,
        "last_cycle_count_at": stock.last_cycle_count_at,
        "avg_daily_units": {
            "value": velocity.value,
            "is_estimate": True,
            "window_days": velocity.window_days,
            "basis": f"{velocity.window_days}-day moving average of units sold (BR-150)",
        },
        "days_of_cover": {
            "value": cover.value,
            "is_estimate": True,
            "basis": "available ÷ average daily units (BR-151)",
            "reason": cover.note,
        },
        "supplier_lead_time_days": detail.supplier.lead_time_days if detail.supplier else None,
        "formulas": FORMULAS,
    }
    return ToolOutput(
        records=[guard.mark(record)],
        notes=["Velocity and days of cover are estimates (BR-152); never present them as facts."],
        untrusted_fields=["records[].ref.label"],
    )


# --- get_inventory_movements ---------------------------------------------------------------------


class GetInventoryMovementsArgs(ProductSelector):
    since: AwareDatetime | None = None
    movement_types: list[MovementType] | None = Field(default=None, max_length=9)
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def _selector(self) -> "GetInventoryMovementsArgs":
        _one_selector([self.product_id, self.sku])
        return self


def get_inventory_movements(
    db: Session, ctx: ToolContext, args: GetInventoryMovementsArgs
) -> ToolOutput:
    check_since(args.since, ctx, "since")
    since = args.since or ctx.as_of - timedelta(days=MOVEMENTS_DEFAULT_DAYS)
    product_id = _resolve_product(db, ctx, args)
    product = db.scalars(
        select(Product).where(Product.store_id == ctx.store_id, Product.id == product_id)
    ).one()
    page = inventory.list_movements(
        db,
        ctx.store_id,
        product_id=product_id,
        movement_types=args.movement_types,
        source=None,
        occurred_from=since,
        occurred_to=None,
        sort="-occurred_at",
        paging=PageParams(page=1, page_size=min(args.limit, ctx.max_rows)),
    )
    guard = TextGuard()
    movements = [
        {
            "movement_type": m.movement_type,
            "on_hand_delta": m.on_hand_delta,
            "incoming_delta": m.incoming_delta,
            "on_hand_after": m.on_hand_after,
            "occurred_at": m.occurred_at,
            "source": m.source,
            "reference": guard(m.reference, REFERENCE_MAX),
            "import": {"ref": ref("import", m.import_id, "Import")} if m.import_id else None,
            "note": guard(m.note, MOVEMENT_NOTE_MAX),
        }
        for m in page.items
    ]
    record = {
        "ref": ref("product", product.id, product_label(product.sku, product.name, guard)),
        "movement_count": page.total,
        "movements": movements,
    }
    return ToolOutput(
        records=[guard.mark(record)],
        truncated=page.total > len(movements),
        data_window_from=since,
        untrusted_fields=[
            "records[].ref.label",
            "records[].movements[].reference",
            "records[].movements[].note",
        ],
    )


SPECS = (
    ToolSpec(
        name="get_product",
        description="Product master data and active exceptions, by id, exact SKU or search.",
        args_model=GetProductArgs,
        permission=Permission.CATALOG_READ,
        row_cap=SEARCH_CAP,
        handler=get_product,
    ),
    ToolSpec(
        name="get_inventory_position",
        description="Current stock of one product with formulas and labelled estimates.",
        args_model=GetInventoryPositionArgs,
        permission=Permission.INVENTORY_READ,
        row_cap=1,
        handler=get_inventory_position,
    ),
    ToolSpec(
        name="get_inventory_movements",
        description="Recent inventory ledger rows of one product, newest first.",
        args_model=GetInventoryMovementsArgs,
        permission=Permission.INVENTORY_READ,
        row_cap=1,
        handler=get_inventory_movements,
    ),
)
