"""Read-side catalog queries: products with their stock position, suppliers and categories.

SELECT only. Stock, health and velocity come from ``inventory.queries`` (one implementation of
BR-101, §2.5 and BR-150). Active exception counts are read from ``exception_entity_link``.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams
from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.catalog.schemas import (
    CategoryList,
    Estimate,
    ProductDetail,
    ProductListItem,
    ProductSort,
    SupplierDetail,
    SupplierOut,
    SupplierRef,
    SupplierSort,
)
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    EntityType,
    ExceptionEntityLink,
    OperationalException,
)
from app.domains.inventory import queries as inventory_queries
from app.domains.inventory.calculations import (
    StockHealth,
    approaching_threshold,
    avg_daily_units,
    days_of_cover,
)


def _count(db: Session, stmt: Select[*tuple[Any, ...]]) -> int:
    return int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)


def list_products(
    db: Session,
    store_id: uuid.UUID,
    *,
    q: str | None,
    status: ProductStatus | None,
    category: str | None,
    supplier_id: uuid.UUID | None,
    health: Sequence[StockHealth] | None,
    sort: ProductSort,
    paging: PageParams,
    factor: Decimal,
) -> Page[ProductListItem]:
    """Products with stock and health. The health filter runs in SQL, so totals stay exact."""
    balance = inventory_queries.balance_subquery(store_id)
    on_hand, reserved, available = inventory_queries.stock_columns(balance)
    stmt = (
        select(Product, Supplier.id, Supplier.name, on_hand, reserved)
        .outerjoin(balance, balance.c.product_id == Product.id)
        .outerjoin(Supplier, (Supplier.id == Product.supplier_id) & (Supplier.store_id == store_id))
        .where(Product.store_id == store_id)
    )
    if q:
        stmt = stmt.where(
            or_(
                Product.sku.icontains(q, autoescape=True),
                Product.name.icontains(q, autoescape=True),
            )
        )
    if status is not None:
        stmt = stmt.where(Product.status == status)
    if category:
        stmt = stmt.where(Product.category == category)
    if supplier_id is not None:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if health:
        health_col = inventory_queries.health_sql(
            on_hand, available, Product.reorder_point, Product.status, factor
        )
        stmt = stmt.where(health_col.in_([h.value for h in health]))

    total = _count(db, stmt)
    columns = {
        "sku": Product.sku,
        "name": Product.name,
        "updated_at": Product.updated_at,
        "available": available,
    }
    column = columns[sort.lstrip("-")]
    primary = column.desc() if sort.startswith("-") else column.asc()
    rows = db.execute(
        stmt.order_by(primary, Product.sku, Product.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()

    items = [
        ProductListItem(
            id=product.id,
            sku=product.sku,
            name=product.name,
            category=product.category,
            status=product.status,
            unit_price=product.unit_price,
            unit_cost=product.unit_cost,
            reorder_point=product.reorder_point,
            reorder_quantity=product.reorder_quantity,
            supplier=SupplierRef(id=sup_id, name=sup_name) if sup_id is not None else None,
            on_hand=oh,
            reserved=rsv,
            available=oh - rsv,
            health=inventory_queries.product_health(
                product.status, oh, oh - rsv, product.reorder_point, factor
            ),
            updated_at=product.updated_at,
        )
        for product, sup_id, sup_name, oh, rsv in rows
    ]
    return Page[ProductListItem](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


def active_exception_count(db: Session, store_id: uuid.UUID, product_id: uuid.UUID) -> int:
    """Active exceptions linked to a product in any role (PRIMARY or AFFECTED)."""
    count = db.scalar(
        select(func.count(func.distinct(OperationalException.id)))
        .join(ExceptionEntityLink, ExceptionEntityLink.exception_id == OperationalException.id)
        .where(
            OperationalException.store_id == store_id,
            ExceptionEntityLink.store_id == store_id,
            ExceptionEntityLink.entity_type == EntityType.PRODUCT,
            ExceptionEntityLink.entity_id == product_id,
            OperationalException.status.in_(ACTIVE_STATUSES),
        )
    )
    return int(count or 0)


def get_product(
    db: Session,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    *,
    as_of: datetime,
    factor: Decimal,
    window_days: int,
) -> ProductDetail:
    """One product with stock, health and the labelled velocity estimates (BR-150..152)."""
    product = db.scalar(
        select(Product).where(Product.store_id == store_id, Product.id == product_id)
    )
    if product is None:
        raise NotFoundError("Product not found.")
    supplier = None
    if product.supplier_id is not None:
        supplier = db.scalar(
            select(Supplier).where(
                Supplier.store_id == store_id, Supplier.id == product.supplier_id
            )
        )

    stock = inventory_queries.get_stock(db, store_id, product.id)
    sold = inventory_queries.units_sold(
        db, store_id, as_of=as_of, window_days=window_days, product_ids=[product.id]
    )
    units = sold.get(product.id, 0)
    daily = avg_daily_units(units, window_days)
    cover = days_of_cover(stock.available, daily)

    return ProductDetail(
        id=product.id,
        sku=product.sku,
        name=product.name,
        category=product.category,
        status=product.status,
        unit_price=product.unit_price,
        unit_cost=product.unit_cost,
        reorder_point=product.reorder_point,
        reorder_quantity=product.reorder_quantity,
        created_at=product.created_at,
        updated_at=product.updated_at,
        supplier=(
            SupplierDetail(
                id=supplier.id, name=supplier.name, lead_time_days=supplier.lead_time_days
            )
            if supplier is not None
            else None
        ),
        stock=stock,
        health=inventory_queries.product_health(
            product.status, stock.on_hand, stock.available, product.reorder_point, factor
        ),
        approaching_threshold=(
            approaching_threshold(product.reorder_point, factor)
            if product.reorder_point > 0
            else None
        ),
        avg_daily_units=Estimate(
            value=daily,
            basis="BR-150",
            window_days=window_days,
            note=f"{units} units sold in the last {window_days} days ÷ {window_days}",
        ),
        days_of_cover=Estimate(
            value=cover,
            basis="BR-151",
            window_days=window_days,
            note=None if cover is not None else "Not enough sales history",
        ),
        active_exception_count=active_exception_count(db, store_id, product.id),
    )


def list_suppliers(
    db: Session,
    store_id: uuid.UUID,
    *,
    q: str | None,
    sort: SupplierSort,
    paging: PageParams,
) -> Page[SupplierOut]:
    product_count = (
        select(func.count(Product.id))
        .where(Product.store_id == store_id, Product.supplier_id == Supplier.id)
        .correlate(Supplier)
        .scalar_subquery()
    )
    stmt = select(Supplier, product_count).where(Supplier.store_id == store_id)
    if q:
        stmt = stmt.where(Supplier.name.icontains(q, autoescape=True))
    total = _count(db, stmt)
    column = {"name": Supplier.name, "lead_time_days": Supplier.lead_time_days}[sort.lstrip("-")]
    primary = (column.desc() if sort.startswith("-") else column.asc()).nulls_last()
    rows = db.execute(
        stmt.order_by(primary, Supplier.name, Supplier.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[SupplierOut](
        items=[
            SupplierOut(
                id=s.id,
                name=s.name,
                lead_time_days=s.lead_time_days,
                contact_ref=s.contact_ref,
                product_count=int(count),
            )
            for s, count in rows
        ],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


def list_categories(db: Session, store_id: uuid.UUID) -> CategoryList:
    """Distinct non-null product categories of the store, alphabetically."""
    rows = db.scalars(
        select(Product.category)
        .where(Product.store_id == store_id, Product.category.is_not(None))
        .distinct()
        .order_by(Product.category)
    ).all()
    return CategoryList(items=[c for c in rows if c is not None])
