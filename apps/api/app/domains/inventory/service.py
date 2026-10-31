"""Inventory ledger, reservation synchronisation and reconciliation (BUSINESS_RULES.md §2).

Callers own the transaction: these functions add/modify rows and flush, but never commit.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BusinessRuleViolationError
from app.domains.inventory.calculations import movement_deltas
from app.domains.inventory.models import (
    InventoryBalance,
    InventoryMovement,
    MovementSource,
    MovementType,
    ReservationStatus,
    StockReservation,
)
from app.domains.orders.models import Order
from app.domains.orders.state import DemandClass, demand_class


def get_balance(
    db: Session, store_id: uuid.UUID, product_id: uuid.UUID, *, lock: bool = False
) -> InventoryBalance:
    """Return the balance row, creating an empty one if the product has none yet."""
    stmt = select(InventoryBalance).where(
        InventoryBalance.store_id == store_id, InventoryBalance.product_id == product_id
    )
    if lock:
        stmt = stmt.with_for_update()
    balance = db.scalar(stmt)
    if balance is None:
        balance = InventoryBalance(
            store_id=store_id, product_id=product_id, on_hand=0, reserved=0, incoming=0
        )
        db.add(balance)
        db.flush()
    return balance


def reference_exists(db: Session, store_id: uuid.UUID, reference: str) -> bool:
    return (
        db.scalar(
            select(InventoryMovement.id).where(
                InventoryMovement.store_id == store_id, InventoryMovement.reference == reference
            )
        )
        is not None
    )


def _on_hand_as_of(db: Session, balance: InventoryBalance, as_of: datetime) -> int:
    later = db.scalar(
        select(func.coalesce(func.sum(InventoryMovement.on_hand_delta), 0)).where(
            InventoryMovement.store_id == balance.store_id,
            InventoryMovement.product_id == balance.product_id,
            InventoryMovement.occurred_at > as_of,
        )
    )
    return balance.on_hand - int(later or 0)


def record_movement(
    db: Session,
    *,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    movement_type: MovementType,
    quantity: int,
    occurred_at: datetime,
    source: MovementSource,
    reference: str | None = None,
    expected_at: datetime | None = None,
    import_id: uuid.UUID | None = None,
    note: str | None = None,
    created_by: uuid.UUID | None = None,
) -> InventoryMovement:
    """Append one ledger row and update the cached balance (BR-110, BR-111)."""
    balance = get_balance(db, store_id, product_id, lock=True)

    if movement_type is MovementType.CYCLE_COUNT:
        if balance.last_cycle_count_at is not None and occurred_at < balance.last_cycle_count_at:
            raise BusinessRuleViolationError(
                "A newer cycle count already exists for this product.", code="STALE_CYCLE_COUNT"
            )
        on_hand_at = _on_hand_as_of(db, balance, occurred_at)
    else:
        on_hand_at = balance.on_hand

    try:
        deltas = movement_deltas(
            movement_type,
            quantity,
            on_hand_at_occurrence=on_hand_at,
            current_incoming=balance.incoming,
        )
    except ValueError as exc:
        raise BusinessRuleViolationError(str(exc), code="INVALID_MOVEMENT_QUANTITY") from exc

    balance.on_hand += deltas.on_hand_delta
    balance.incoming += deltas.incoming_delta
    if movement_type is MovementType.CYCLE_COUNT:
        balance.last_cycle_count_at = occurred_at
    if (
        movement_type is MovementType.INCOMING_EXPECTED
        and expected_at is not None
        and (balance.incoming_eta is None or expected_at < balance.incoming_eta)
    ):
        balance.incoming_eta = expected_at
    if balance.incoming == 0:
        balance.incoming_eta = None

    movement = InventoryMovement(
        store_id=store_id,
        product_id=product_id,
        movement_type=movement_type,
        on_hand_delta=deltas.on_hand_delta,
        incoming_delta=deltas.incoming_delta,
        on_hand_after=balance.on_hand,
        incoming_after=balance.incoming,
        occurred_at=occurred_at,
        source=source,
        reference=reference,
        import_id=import_id,
        note=note,
        created_by=created_by,
    )
    db.add(movement)
    db.flush()
    return movement


def _ensure_shipment_movement(
    db: Session, order: Order, item_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> None:
    """BR-130/131: one SHIPMENT movement per order line, only after the latest cycle count."""
    reference = f"order_item:{item_id}"
    if reference_exists(db, order.store_id, reference):
        return
    shipped_at = order.shipped_at
    if shipped_at is None:  # guarded by order validation; defensive
        return
    balance = get_balance(db, order.store_id, product_id)
    if balance.last_cycle_count_at is not None and shipped_at <= balance.last_cycle_count_at:
        return  # the count already reflects this shipment
    record_movement(
        db,
        store_id=order.store_id,
        product_id=product_id,
        movement_type=MovementType.SHIPMENT,
        quantity=quantity,
        occurred_at=shipped_at,
        source=MovementSource.ORDER,
        reference=reference,
        note=f"Order {order.order_number}",
    )


def sync_reservations(
    db: Session, store_id: uuid.UUID, order_ids: Iterable[uuid.UUID], *, now: datetime
) -> set[uuid.UUID]:
    """Bring reservations of the given orders in line with their status (BR-120..123).

    Idempotent. Returns the product ids whose ``reserved`` balance was recomputed.
    """
    ids = list(set(order_ids))
    if not ids:
        return set()
    orders = db.scalars(
        select(Order)
        .where(Order.store_id == store_id, Order.id.in_(ids))
        .options(selectinload(Order.items))
    ).all()
    existing = {
        r.order_item_id: r
        for r in db.scalars(
            select(StockReservation).where(
                StockReservation.store_id == store_id, StockReservation.order_id.in_(ids)
            )
        ).all()
    }
    affected: set[uuid.UUID] = set()

    for order in orders:
        target = demand_class(order.status, order.fulfillment_status)
        for item in order.items:
            affected.add(item.product_id)
            reservation = existing.get(item.id)
            if target is DemandClass.COMMITTED:
                if reservation is None:
                    db.add(
                        StockReservation(
                            store_id=store_id,
                            product_id=item.product_id,
                            order_id=order.id,
                            order_item_id=item.id,
                            quantity=item.quantity,
                            status=ReservationStatus.ACTIVE,
                            activated_at=now,
                        )
                    )
                else:
                    # A line whose SKU changed must release stock on the previous product too.
                    affected.add(reservation.product_id)
                    if reservation.status is not ReservationStatus.ACTIVE:
                        reservation.status = ReservationStatus.ACTIVE
                        reservation.activated_at = now
                        reservation.closed_at = None
                    reservation.quantity = item.quantity
                    reservation.product_id = item.product_id
            elif target is DemandClass.FULFILLED:
                closed_at = order.shipped_at or now
                if reservation is None:
                    db.add(
                        StockReservation(
                            store_id=store_id,
                            product_id=item.product_id,
                            order_id=order.id,
                            order_item_id=item.id,
                            quantity=item.quantity,
                            status=ReservationStatus.CONSUMED,
                            closed_at=closed_at,
                        )
                    )
                elif reservation.status is not ReservationStatus.CONSUMED:
                    reservation.status = ReservationStatus.CONSUMED
                    reservation.closed_at = closed_at
                _ensure_shipment_movement(db, order, item.id, item.product_id, item.quantity)
            elif reservation is not None and reservation.status is ReservationStatus.ACTIVE:
                reservation.status = ReservationStatus.RELEASED
                reservation.closed_at = now

    db.flush()
    recompute_reserved(db, store_id, affected)
    return affected


def recompute_reserved(db: Session, store_id: uuid.UUID, product_ids: Iterable[uuid.UUID]) -> None:
    ids = list(set(product_ids))
    if not ids:
        return
    sums = dict(
        db.execute(
            select(StockReservation.product_id, func.sum(StockReservation.quantity))
            .where(
                StockReservation.store_id == store_id,
                StockReservation.product_id.in_(ids),
                StockReservation.status == ReservationStatus.ACTIVE,
            )
            .group_by(StockReservation.product_id)
        ).all()
    )
    for product_id in ids:
        balance = get_balance(db, store_id, product_id, lock=True)
        balance.reserved = int(sums.get(product_id) or 0)
    db.flush()


@dataclass(frozen=True)
class BalanceDrift:
    product_id: uuid.UUID
    field: str
    stored: int
    computed: int


def reconcile(db: Session, store_id: uuid.UUID) -> list[BalanceDrift]:
    """BR-104: compare cached balances with the ledger and reservations. Reports, never fixes."""
    ledger = {
        pid: (int(oh), int(inc))
        for pid, oh, inc in db.execute(
            select(
                InventoryMovement.product_id,
                func.sum(InventoryMovement.on_hand_delta),
                func.sum(InventoryMovement.incoming_delta),
            )
            .where(InventoryMovement.store_id == store_id)
            .group_by(InventoryMovement.product_id)
        ).all()
    }
    reserved = {
        pid: int(qty)
        for pid, qty in db.execute(
            select(StockReservation.product_id, func.sum(StockReservation.quantity))
            .where(
                StockReservation.store_id == store_id,
                StockReservation.status == ReservationStatus.ACTIVE,
            )
            .group_by(StockReservation.product_id)
        ).all()
    }
    drifts: list[BalanceDrift] = []
    for balance in db.scalars(
        select(InventoryBalance).where(InventoryBalance.store_id == store_id)
    ).all():
        on_hand, incoming = ledger.get(balance.product_id, (0, 0))
        checks = (
            ("on_hand", balance.on_hand, on_hand),
            ("incoming", balance.incoming, incoming),
            ("reserved", balance.reserved, reserved.get(balance.product_id, 0)),
        )
        drifts.extend(
            BalanceDrift(balance.product_id, field, stored, computed)
            for field, stored, computed in checks
            if stored != computed
        )
    return drifts
