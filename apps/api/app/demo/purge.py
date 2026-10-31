"""Remove an organization and all of its store data (demo reset only)."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domains.identity.models import Organization, Store
from app.domains.orders.models import OrderItem


def purge_organization(db: Session, organization_id: uuid.UUID) -> None:
    """Delete the organization; foreign keys cascade to every store-scoped table.

    Order lines go first: ``order_item.product_id`` is ON DELETE RESTRICT (a product with sales
    history must never disappear in normal operation), so lines must be gone before the cascade
    reaches products.
    """
    store_ids = select(Store.id).where(Store.organization_id == organization_id)
    db.execute(delete(OrderItem).where(OrderItem.store_id.in_(store_ids)))
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.flush()
