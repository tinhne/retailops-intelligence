"""HTTP endpoints for the catalog module. See docs/architecture/API_CONVENTIONS.md."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.clock import utcnow
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.catalog import queries
from app.domains.catalog.models import ProductStatus
from app.domains.catalog.schemas import (
    CategoryList,
    ProductDetail,
    ProductListItem,
    ProductSort,
    SupplierOut,
    SupplierSort,
)
from app.domains.identity import store_service
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext
from app.domains.inventory.calculations import StockHealth

router = APIRouter(prefix="/stores/{store_id}", tags=["catalog"])


@router.get("/products", response_model=Page[ProductListItem])
def list_products(
    q: str | None = Query(None, max_length=100, description="Substring of SKU or name."),
    status: ProductStatus | None = None,
    category: str | None = Query(None, max_length=100),
    supplier_id: uuid.UUID | None = None,
    health: list[StockHealth] | None = Query(None, description="Repeatable. ACTIVE products."),
    sort: ProductSort = "sku",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.CATALOG_READ)),
    db: Session = Depends(get_db),
) -> Page[ProductListItem]:
    settings = store_service.get_settings(db, ctx.store_id)
    return queries.list_products(
        db,
        ctx.store_id,
        q=q,
        status=status,
        category=category,
        supplier_id=supplier_id,
        health=health,
        sort=sort,
        paging=paging,
        factor=settings.approaching_reorder_factor,
    )


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: uuid.UUID,
    ctx: StoreContext = Depends(require_permission(Permission.CATALOG_READ)),
    db: Session = Depends(get_db),
) -> ProductDetail:
    settings = store_service.get_settings(db, ctx.store_id)
    return queries.get_product(
        db,
        ctx.store_id,
        product_id,
        as_of=utcnow(),
        factor=settings.approaching_reorder_factor,
        window_days=settings.velocity_window_days,
    )


@router.get("/suppliers", response_model=Page[SupplierOut])
def list_suppliers(
    q: str | None = Query(None, max_length=100),
    sort: SupplierSort = "name",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.CATALOG_READ)),
    db: Session = Depends(get_db),
) -> Page[SupplierOut]:
    return queries.list_suppliers(db, ctx.store_id, q=q, sort=sort, paging=paging)


@router.get("/categories", response_model=CategoryList)
def list_categories(
    ctx: StoreContext = Depends(require_permission(Permission.CATALOG_READ)),
    db: Session = Depends(get_db),
) -> CategoryList:
    return queries.list_categories(db, ctx.store_id)
