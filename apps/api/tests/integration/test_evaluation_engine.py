"""Evaluation engine mechanics: advisory lock, failure isolation, snapshot queries (T-053)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.domains.catalog.models import ProductStatus
from app.domains.exceptions import engine as evaluation_engine
from app.domains.exceptions.engine import (
    EVALUATION_LOCK_NAMESPACE,
    SKIPPED_MESSAGE,
    _Reconciler,
    advisory_lock_key,
    run_evaluation,
)
from app.domains.exceptions.models import (
    EvaluationRun,
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionEvent,
    ExceptionStatus,
    ExceptionType,
    OperationalException,
)
from app.domains.exceptions.rules.base import Rule
from app.domains.exceptions.rules.registry import UnknownRuleError
from app.domains.exceptions.snapshot import RuleSettings, load_snapshot
from app.domains.inventory.models import MovementType
from app.domains.orders.models import OrderStatus, PaymentStatus
from tests.factories import Tenant, create_tenant
from tests.factories_exceptions import (
    T0,
    LineSpec,
    OrderSpec,
    adjust_stock,
    evaluate,
    exceptions_for,
    make_order,
    make_product,
    one_exception,
    set_stock,
)

pytestmark = pytest.mark.integration
H = timedelta(hours=1)


@pytest.fixture
def tenant(db: Session) -> Tenant:
    return create_tenant(db)


def test_advisory_lock_held_elsewhere_records_a_skipped_run(
    db: Session, engine: Engine, tenant: Tenant
) -> None:
    make_product(db, tenant, "A-1", reorder_point=0)
    db.commit()
    with engine.connect() as other, other.begin():
        other.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:ns AS integer), CAST(:key AS integer))"),
            {"ns": EVALUATION_LOCK_NAMESPACE, "key": advisory_lock_key(tenant.store.id)},
        )
        run = run_evaluation(db, tenant.store.id, trigger=EvaluationTrigger.SCHEDULED, as_of=T0)
        db.commit()

        assert run.status is EvaluationStatus.SKIPPED
        assert run.error == SKIPPED_MESSAGE
        assert run.counts == {}
        assert exceptions_for(db, tenant) == []

    # Once the other transaction ends, the next run proceeds.
    assert evaluate(db, tenant, T0).status is EvaluationStatus.SUCCEEDED
    assert len(exceptions_for(db, tenant)) == 1


def test_lock_is_per_store(db: Session, engine: Engine, tenant: Tenant) -> None:
    other_tenant = create_tenant(db, "zenith")
    with engine.connect() as other, other.begin():
        other.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:ns AS integer), CAST(:key AS integer))"),
            {"ns": EVALUATION_LOCK_NAMESPACE, "key": advisory_lock_key(tenant.store.id)},
        )
        assert advisory_lock_key(other_tenant.store.id) != advisory_lock_key(tenant.store.id)
        run = evaluate(db, other_tenant, T0)
        assert run.status is EvaluationStatus.SUCCEEDED


def test_reconciliation_failure_rolls_back_every_exception_change(
    db: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed run commits no exception changes; only the FAILED run row persists."""
    item = make_product(db, tenant, "A-1", reorder_point=0)
    evaluate(db, tenant, T0)
    existing = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    make_product(db, tenant, "A-2", reorder_point=0)  # would create a second exception
    adjust_stock(db, tenant, item, MovementType.RECEIPT, 5, T0 + H)  # would auto-resolve

    def boom(self: _Reconciler) -> None:
        raise RuntimeError("link sync exploded")

    monkeypatch.setattr(_Reconciler, "_sync_links", boom)
    db.commit()
    run = run_evaluation(db, tenant.store.id, trigger=EvaluationTrigger.MANUAL, as_of=T0 + 2 * H)
    db.commit()

    assert run.status is EvaluationStatus.FAILED
    assert run.error == "RuntimeError: link sync exploded"
    assert run.finished_at is not None
    assert run.counts == {}
    rows = exceptions_for(db, tenant)
    assert [r.id for r in rows] == [existing.id]
    assert rows[0].status is ExceptionStatus.OPEN
    assert rows[0].version == 1
    assert db.scalar(select(func.count()).select_from(ExceptionEvent)) == 1
    statuses = db.scalars(select(EvaluationRun.status).order_by(EvaluationRun.started_at)).all()
    assert statuses == [EvaluationStatus.SUCCEEDED, EvaluationStatus.FAILED]


def test_rule_error_marks_the_run_failed_without_raising(
    db: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> list[object]:
        raise ZeroDivisionError("bad math")

    rule = Rule("BROKEN@1", ExceptionType.DATA_NEGATIVE_ON_HAND, None, broken)  # type: ignore[arg-type]
    monkeypatch.setattr(evaluation_engine, "select_rules", lambda _ids: (rule,))

    run = evaluate(db, tenant, T0)

    assert run.status is EvaluationStatus.FAILED
    assert run.error == "ZeroDivisionError: bad math"


def test_unknown_rule_ids_are_rejected_before_running(db: Session, tenant: Tenant) -> None:
    with pytest.raises(UnknownRuleError) as info:
        run_evaluation(
            db,
            tenant.store.id,
            trigger=EvaluationTrigger.MANUAL,
            as_of=T0,
            rule_ids=["INV-OVERSOLD@1", "NOPE@9"],
        )
    assert info.value.code == "UNKNOWN_RULE"
    assert db.scalar(select(func.count()).select_from(EvaluationRun)) == 0


def test_snapshot_velocity_window_excludes_unsold_statuses(db: Session, tenant: Tenant) -> None:
    """BR-150: lines placed in (as_of − 28 d, as_of]; CANCELLED, PAYMENT_FAILED, CREATED,
    PAYMENT_PENDING and orders refunded before shipping do not count."""
    item = make_product(db, tenant, "A-1", reorder_point=0)
    set_stock(db, tenant, item, 100, T0 - 60 * 24 * H)
    inside = T0 - 27 * 24 * H

    def order(
        number: str,
        status: OrderStatus,
        qty: int,
        placed: datetime = inside,
        shipped_at: datetime | None = None,
        cancelled_at: datetime | None = None,
    ) -> None:
        spec = OrderSpec(
            number,
            status,
            [LineSpec(item, qty)],
            placed_at=placed,
            shipped_at=shipped_at,
            cancelled_at=cancelled_at,
        )
        make_order(db, tenant, spec)

    order("1", OrderStatus.PAID, 2)
    order("2", OrderStatus.SHIPPED, 3, shipped_at=inside + H)
    order("3", OrderStatus.CANCELLED, 50, cancelled_at=inside + H)
    order("4", OrderStatus.CREATED, 50)
    order("5", OrderStatus.PAYMENT_PENDING, 50)
    order("6", OrderStatus.PAID, 50, placed=T0 - 28 * 24 * H)  # exactly at the window start
    order("7", OrderStatus.PAID, 50, placed=T0 + H)  # after as_of
    make_order(
        db,
        tenant,
        OrderSpec(
            "8",
            OrderStatus.CANCELLED,
            [LineSpec(item, 50)],
            placed_at=inside,
            cancelled_at=inside + H,
            payment_status=PaymentStatus.PAID,
        ),
    )
    db.commit()

    snap = load_snapshot(db, tenant.store.id, T0, RuleSettings())

    assert snap.products[item.id].units_sold_in_window == 5
    # pending demand and committed lines come from the same snapshot
    assert snap.pending_demand(item.id) == 100
    assert {line.order_number for line in snap.committed_lines} == {"1", "6", "7"}


def test_snapshot_excludes_orders_refunded_before_shipping_from_velocity(
    db: Session, tenant: Tenant
) -> None:
    item = make_product(db, tenant, "A-1", reorder_point=0)
    placed = T0 - 2 * 24 * H
    make_order(
        db,
        tenant,
        OrderSpec(
            "R-1",
            OrderStatus.CANCELLED,
            [LineSpec(item, 4)],
            placed_at=placed,
            cancelled_at=placed + H,
            payment_status=PaymentStatus.PAID,
        ),
    )
    make_order(
        db,
        tenant,
        OrderSpec(
            "R-1",
            OrderStatus.REFUNDED,
            [LineSpec(item, 4)],
            placed_at=placed,
            cancelled_at=placed + H,
            paid_at=placed,
        ),
    )
    db.commit()

    snap = load_snapshot(db, tenant.store.id, T0, RuleSettings())

    assert snap.products[item.id].units_sold_in_window == 0


def test_negative_on_hand_end_to_end_suppresses_inventory_rules(
    db: Session, tenant: Tenant
) -> None:
    """BR-402a: on hand 1 − 3 damaged = −2. Only DATA_NEGATIVE_ON_HAND is raised, no oversold."""
    item = make_product(db, tenant, "A-1", reorder_point=5, status=ProductStatus.ACTIVE)
    set_stock(db, tenant, item, 1, T0 - 5 * H)
    adjust_stock(db, tenant, item, MovementType.DAMAGE, 3, T0 - 4 * H)

    evaluate(db, tenant, T0)

    rows = exceptions_for(db, tenant)
    assert [r.exception_type for r in rows] == [ExceptionType.DATA_NEGATIVE_ON_HAND]
    movements = rows[0].evidence["records"]["recent_movements"]
    assert [m["movement_type"] for m in movements] == ["DAMAGE", "CYCLE_COUNT"]
    assert rows[0].evidence["records"]["last_cycle_count"][0]["on_hand_after"] == 1


def test_quiet_refresh_does_not_bump_version_but_events_do(db: Session, tenant: Tenant) -> None:
    item = make_product(db, tenant, "A-1", reorder_point=0)
    evaluate(db, tenant, T0)
    for hour in (1, 2, 3):
        evaluate(db, tenant, T0 + hour * H)
    exc = db.scalars(select(OperationalException)).one()
    assert (exc.version, exc.detection_count) == (1, 4)
    adjust_stock(db, tenant, item, MovementType.INCOMING_EXPECTED, 10, T0 + 4 * H)
    evaluate(db, tenant, T0 + 5 * H)  # incoming 0 → 10 is material
    db.expire_all()
    assert db.scalars(select(OperationalException)).one().version == 2
