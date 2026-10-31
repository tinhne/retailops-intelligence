"""Store-scoped queries for the exceptions module.

Identity, catalog and orders tables are read here only to resolve display labels and assignee
eligibility (SYSTEM_ARCHITECTURE.md §4: ``exceptions → identity`` validates assignees).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.domains.catalog.models import Product
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    ExceptionSequence,
    OperationalException,
)
from app.domains.identity.models import Membership, Store, User
from app.domains.identity.permissions import Permission, permissions_for
from app.domains.orders.models import Order

REFERENCE_PREFIX = "EXC-"
FIRST_REFERENCE = 1001


def get_exception(
    db: Session, store_id: uuid.UUID, exception_id: uuid.UUID, *, for_update: bool = False
) -> OperationalException:
    """Load one exception of the store (404 if it belongs to another store or does not exist)."""
    stmt = select(OperationalException).where(
        OperationalException.store_id == store_id, OperationalException.id == exception_id
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    exc = db.scalar(stmt)
    if exc is None:
        raise NotFoundError("Exception not found.")
    return exc


def other_active_occurrence(
    db: Session, store_id: uuid.UUID, dedup_key: str, exclude_id: uuid.UUID
) -> OperationalException | None:
    return db.scalar(
        select(OperationalException).where(
            OperationalException.store_id == store_id,
            OperationalException.dedup_key == dedup_key,
            OperationalException.id != exclude_id,
            OperationalException.status.in_(ACTIVE_STATUSES),
        )
    )


def allocate_reference(db: Session, store_id: uuid.UUID) -> str:
    """Next ``EXC-nnnn`` reference from the per-store counter.

    The UPDATE takes a row lock on the store's counter, so concurrent allocations serialize.
    """
    db.execute(
        pg_insert(ExceptionSequence)
        .values(store_id=store_id, next_value=FIRST_REFERENCE)
        .on_conflict_do_nothing(index_elements=[ExceptionSequence.store_id])
    )
    value = db.execute(
        update(ExceptionSequence)
        .where(ExceptionSequence.store_id == store_id)
        .values(next_value=ExceptionSequence.next_value + 1)
        .returning(ExceptionSequence.next_value - 1)
        .execution_options(synchronize_session=False)
    ).scalar_one()
    return f"{REFERENCE_PREFIX}{value}"


def eligible_assignee_ids(
    db: Session, store_id: uuid.UUID, user_ids: Iterable[uuid.UUID] | None = None
) -> set[uuid.UUID]:
    """Active members of the store's organization whose role grants ``exceptions.work``."""
    stmt = (
        select(Membership.user_id, Membership.role)
        .join(Store, Store.organization_id == Membership.organization_id)
        .join(User, User.id == Membership.user_id)
        .where(Store.id == store_id, User.is_active.is_(True))
    )
    if user_ids is not None:
        ids = list(set(user_ids))
        if not ids:
            return set()
        stmt = stmt.where(Membership.user_id.in_(ids))
    return {
        user_id
        for user_id, role in db.execute(stmt).all()
        if Permission.EXCEPTIONS_WORK in permissions_for(role)
    }


def user_names(db: Session, user_ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = list({uid for uid in user_ids if uid is not None})
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    return {uid: name for uid, name in rows}


def product_labels(
    db: Session, store_id: uuid.UUID, product_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    """``{product_id: (sku, name)}`` for products of the store."""
    ids = list(set(product_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(Product.id, Product.sku, Product.name).where(
            Product.store_id == store_id, Product.id.in_(ids)
        )
    ).all()
    return {pid: (sku, name) for pid, sku, name in rows}


def order_labels(
    db: Session, store_id: uuid.UUID, order_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """``{order_id: order_number}`` for orders of the store."""
    ids = list(set(order_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(Order.id, Order.order_number).where(Order.store_id == store_id, Order.id.in_(ids))
    ).all()
    return {oid: number for oid, number in rows}
