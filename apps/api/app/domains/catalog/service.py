"""Product master data write path: product upsert by SKU and supplier upsert by name.

Used by the products import (BR-608). Callers validate row shape first; these functions add or
modify rows and flush, but never commit.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domains.catalog.models import Product, ProductStatus, Supplier


@dataclass(frozen=True)
class ProductData:
    """A validated product row. ``supplier_name`` None means "no supplier"."""

    sku: str
    name: str
    category: str | None
    status: ProductStatus
    unit_price: Decimal
    unit_cost: Decimal | None
    reorder_point: int
    reorder_quantity: int | None
    supplier_name: str | None


_PRODUCT_FIELDS = (
    "name",
    "category",
    "status",
    "unit_price",
    "unit_cost",
    "reorder_point",
    "reorder_quantity",
)


def find_products_by_sku(
    db: Session, store_id: uuid.UUID, skus: Iterable[str]
) -> dict[str, Product]:
    """Products keyed by SKU (BR-506: exact match after trimming), with suppliers loaded."""
    wanted = sorted(set(skus))
    if not wanted:
        return {}
    rows = db.scalars(
        select(Product)
        .where(Product.store_id == store_id, Product.sku.in_(wanted))
        .options(selectinload(Product.supplier))
    ).all()
    return {product.sku: product for product in rows}


def find_suppliers_by_name(
    db: Session, store_id: uuid.UUID, names: Iterable[str]
) -> dict[str, Supplier]:
    wanted = sorted(set(names))
    if not wanted:
        return {}
    rows = db.scalars(
        select(Supplier).where(Supplier.store_id == store_id, Supplier.name.in_(wanted))
    ).all()
    return {supplier.name: supplier for supplier in rows}


def product_changes(existing: Product, data: ProductData) -> list[str]:
    """Names of the fields an upsert of ``data`` would change on ``existing``."""
    changed = [
        field for field in _PRODUCT_FIELDS if getattr(existing, field) != getattr(data, field)
    ]
    current_supplier = existing.supplier.name if existing.supplier is not None else None
    if current_supplier != data.supplier_name:
        changed.append("supplier_name")
    return changed


def upsert_supplier(
    db: Session, *, store_id: uuid.UUID, name: str, lead_time_days: int | None
) -> Supplier:
    """Create the supplier if new. ``lead_time_days`` None keeps the stored lead time."""
    supplier = db.scalar(
        select(Supplier).where(Supplier.store_id == store_id, Supplier.name == name)
    )
    if supplier is None:
        supplier = Supplier(store_id=store_id, name=name, lead_time_days=lead_time_days)
        db.add(supplier)
    elif lead_time_days is not None and supplier.lead_time_days != lead_time_days:
        supplier.lead_time_days = lead_time_days
    db.flush()
    return supplier


def upsert_product(
    db: Session, *, store_id: uuid.UUID, data: ProductData, supplier_id: uuid.UUID | None
) -> tuple[Product, bool]:
    """Insert or update the product with this SKU. Returns ``(product, created)``."""
    product = db.scalar(
        select(Product).where(Product.store_id == store_id, Product.sku == data.sku)
    )
    created = product is None
    if product is None:
        product = Product(store_id=store_id, sku=data.sku)
        db.add(product)
    for field in _PRODUCT_FIELDS:
        if getattr(product, field) != getattr(data, field):
            setattr(product, field, getattr(data, field))
    if product.supplier_id != supplier_id:
        product.supplier_id = supplier_id
    db.flush()
    return product, created
