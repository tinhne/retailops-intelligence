"""Reconciliation of findings against stored exceptions, row by row of STATE_MACHINES.md §3.3
(R1–R8 in EXCEPTION_MANAGEMENT.md §5), plus supersede (BR-401) and links/priority upkeep."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product
from app.domains.exceptions import service
from app.domains.exceptions.engine import VERIFICATION_GRACE_HOURS
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    ActorType,
    DismissalReason,
    EntityType,
    EvaluationStatus,
    ExceptionAssignment,
    ExceptionEntityLink,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionStatus,
    ExceptionType,
    LinkRole,
    OperationalException,
    ResolutionCode,
    Severity,
)
from app.domains.identity.models import User
from app.domains.identity.permissions import Role
from app.domains.identity.service import StoreContext, store_context
from app.domains.imports.models import DataImport, ImportStatus, ImportType
from app.domains.inventory.models import MovementType
from app.domains.orders.models import Order, OrderStatus
from tests.factories import Tenant, create_tenant, create_user
from tests.factories_exceptions import (
    T0,
    LineSpec,
    OrderSpec,
    adjust_stock,
    evaluate,
    event_types,
    exceptions_for,
    make_order,
    make_product,
    one_exception,
    set_stock,
)

pytestmark = pytest.mark.integration
OVERDUE = ExceptionType.ORDER_FULFILLMENT_OVERDUE
H = timedelta(hours=1)


def _ctx(db: Session, tenant: Tenant, user: User) -> StoreContext:
    return store_context(db, user, tenant.store.id)


def _overdue_order(
    db: Session, tenant: Tenant, product: Product, number: str = "KHK-1001", ship_by: datetime = T0
) -> Order:
    return make_order(
        db,
        tenant,
        OrderSpec(
            number,
            OrderStatus.PAID,
            [LineSpec(product, 1, "120.00")],
            placed_at=ship_by - 50 * H,
            paid_at=ship_by - 48 * H,
            ship_by=ship_by,
        ),
    )


def _ship(db: Session, tenant: Tenant, order: Order, product: Product, at: datetime) -> None:
    make_order(
        db,
        tenant,
        OrderSpec(
            order.order_number,
            OrderStatus.SHIPPED,
            [LineSpec(product, 1, "120.00")],
            placed_at=order.placed_at,
            paid_at=order.paid_at,
            ship_by=order.ship_by,
            shipped_at=at,
        ),
        now=at,
    )


@pytest.fixture
def tenant(db: Session) -> Tenant:
    return create_tenant(db)


@pytest.fixture
def product(db: Session, tenant: Tenant) -> Product:
    item = make_product(db, tenant, "KH-MUG-01", reorder_point=0)
    set_stock(db, tenant, item, 50, T0 - 100 * H)
    return item


# --- R1: create ---------------------------------------------------------------------------------


def test_r1_new_condition_creates_open_exception_with_reference_links_priority_and_due(
    db: Session, tenant: Tenant
) -> None:
    mug = make_product(db, tenant, "KH-MUG-01", reorder_point=0, unit_price="18.00")
    set_stock(db, tenant, mug, 1, T0 - 10 * H)
    first = make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-1001",
            OrderStatus.PAID,
            [LineSpec(mug, 1, "18.00")],
            paid_at=T0 - 3 * H,
            ship_by=T0 + 40 * H,
        ),
    )
    second = make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-1002",
            OrderStatus.PAID,
            [LineSpec(mug, 2, "18.00")],
            paid_at=T0 - 2 * H,
            ship_by=T0 + 10 * H,
        ),
    )

    run = evaluate(db, tenant, T0)

    assert run.status is EvaluationStatus.SUCCEEDED
    assert run.counts["created"] == 1
    assert run.finished_at is not None
    assert run.duration_ms is not None
    assert "INV-OVERSOLD@1" in run.rules
    exc = one_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, mug.id)
    assert exc.reference == "EXC-1001"
    assert exc.status is ExceptionStatus.OPEN
    assert exc.severity is Severity.CRITICAL
    assert exc.dedup_key == f"INVENTORY_OVERSOLD:product:{mug.id}"
    assert exc.exposure_amount == Decimal("36.00")  # KHK-1002 uncovered: 2 × 18.00
    assert exc.affected_order_count == 1
    assert exc.deadline_at == T0 + 10 * H
    # 50 + 3 + round(15 × log10(37)/log10(5001)) = 6 + 8 (ship-by within 24 h) + 0 = 67
    assert (exc.priority_score, exc.priority_band.value) == (67, "P2")
    assert exc.due_at == T0 + 4 * H  # CRITICAL response target, earlier than the deadline
    assert exc.first_detected_at == exc.last_detected_at == T0
    assert exc.version == 1
    assert event_types(db, exc) == [ExceptionEventType.DETECTED]
    links = {
        (link.entity_type, link.entity_id): link.role
        for link in db.scalars(
            select(ExceptionEntityLink).where(ExceptionEntityLink.exception_id == exc.id)
        )
    }
    assert links == {
        (EntityType.PRODUCT, mug.id): LinkRole.PRIMARY,
        (EntityType.ORDER, second.id): LinkRole.AFFECTED,
    }
    assert first.id not in {eid for _, eid in links}


def test_references_are_allocated_sequentially_per_store(db: Session, tenant: Tenant) -> None:
    other = create_tenant(db, "zenith")
    for t in (tenant, other):
        for sku in ("A-1", "A-2"):
            make_product(db, t, sku, reorder_point=0)  # no stock → out of stock

    evaluate(db, tenant, T0)
    evaluate(db, other, T0)

    assert sorted(e.reference for e in exceptions_for(db, tenant)) == ["EXC-1001", "EXC-1002"]
    assert sorted(e.reference for e in exceptions_for(db, other)) == ["EXC-1001", "EXC-1002"]


# --- R2: refresh ---------------------------------------------------------------------------------


def test_r2_refresh_without_material_change_writes_no_event_and_keeps_version(
    db: Session, tenant: Tenant, product: Product
) -> None:
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 2 * H)
    exc = one_exception(db, tenant, OVERDUE, order.id)

    run = evaluate(db, tenant, T0 + 3 * H)  # only "hours overdue" moved

    assert run.counts["unchanged"] == 1
    assert run.counts["refreshed"] == 0
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert event_types(db, exc) == [ExceptionEventType.DETECTED]
    assert exc.version == 1
    assert exc.detection_count == 2
    assert exc.last_detected_at == T0 + 3 * H
    hours = next(f for f in exc.evidence["facts"] if f["key"] == "hours_overdue")
    assert hours["value"] == "3.0"


def test_r2_priority_is_recomputed_every_run_so_the_age_component_moves(
    db: Session, tenant: Tenant, product: Product
) -> None:
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    before = one_exception(db, tenant, OVERDUE, order.id).priority_score

    evaluate(db, tenant, T0 + 23 * H)
    evaluate(db, tenant, T0 + 25 * H)  # 1 whole day open; also HIGH now (> 24 h overdue)

    exc = one_exception(db, tenant, OVERDUE, order.id)
    age = next(c for c in exc.priority_breakdown["components"] if c["key"] == "age")
    assert age["points"] == 2
    assert exc.priority_score == before + 15 + 2  # MEDIUM 20 → HIGH 35, plus 2 age points
    assert exc.priority_breakdown["due"]["anchor_at"] == (T0 + 1 * H).isoformat()


def test_r2_material_evidence_change_writes_evidence_updated_with_previous_snapshot(
    db: Session, tenant: Tenant
) -> None:
    mug = make_product(db, tenant, "KH-MUG-01", reorder_point=0)
    set_stock(db, tenant, mug, 1, T0 - 10 * H)
    for number, qty in (("KHK-1001", 1), ("KHK-1002", 1)):
        make_order(
            db,
            tenant,
            OrderSpec(number, OrderStatus.PAID, [LineSpec(mug, qty)], paid_at=T0 - 2 * H),
        )
    evaluate(db, tenant, T0)
    make_order(
        db,
        tenant,
        OrderSpec("KHK-1003", OrderStatus.PAID, [LineSpec(mug, 2)], paid_at=T0 - 1 * H),
    )

    run = evaluate(db, tenant, T0 + 1 * H)

    assert run.counts["refreshed"] == 1
    exc = one_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, mug.id)
    assert event_types(db, exc) == [
        ExceptionEventType.DETECTED,
        ExceptionEventType.EVIDENCE_UPDATED,
    ]
    assert exc.version == 2  # the version moves only with events
    event = db.scalars(
        select(ExceptionEvent).where(
            ExceptionEvent.exception_id == exc.id,
            ExceptionEvent.event_type == ExceptionEventType.EVIDENCE_UPDATED,
        )
    ).one()
    previous_facts = {f["key"]: f["value"] for f in event.payload["previous"]["evidence"]["facts"]}
    assert previous_facts["shortage"] == 1
    assert {"shortage", "reserved"} <= set(event.payload["changed_facts"])
    assert event.actor_type is ActorType.SYSTEM
    assert event.evaluation_run_id == run.id
    assert exc.affected_order_count == 2


def test_r2_severity_change_writes_event_and_recomputes_due_date(
    db: Session, tenant: Tenant, product: Product
) -> None:
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)  # MEDIUM: due = detection + 72 h
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert (exc.severity, exc.due_at) == (Severity.MEDIUM, T0 + 73 * H)

    run = evaluate(db, tenant, T0 + 25 * H)  # overdue > 24 h → HIGH

    assert run.counts["refreshed"] == 1
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.severity is Severity.HIGH
    assert exc.due_at == T0 + 25 * H  # first detection + 24 h
    assert event_types(db, exc) == [
        ExceptionEventType.DETECTED,
        ExceptionEventType.SEVERITY_CHANGED,
    ]


def test_r2_severity_change_keeps_a_manual_due_date_override(
    db: Session, tenant: Tenant, product: Product
) -> None:
    manager = create_user(db, tenant, Role.MANAGER)
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    exc = one_exception(db, tenant, OVERDUE, order.id)
    override = T0 + 200 * H
    service.set_due_date(
        db,
        _ctx(db, tenant, manager),
        exc.id,
        due_at=override,
        note=None,
        expected_version=None,
        now=T0 + 2 * H,
    )

    evaluate(db, tenant, T0 + 25 * H)

    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.severity is Severity.HIGH
    assert (exc.due_at, exc.due_at_overridden) == (override, True)


# --- R3: auto-resolve, and only rules that ran --------------------------------------------------


def test_r3_cleared_condition_auto_resolves_with_condition_cleared(
    db: Session, tenant: Tenant, product: Product
) -> None:
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    _ship(db, tenant, order, product, T0 + 2 * H)

    run = evaluate(db, tenant, T0 + 3 * H)

    assert run.counts["resolved"] == 1
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.status is ExceptionStatus.RESOLVED
    assert exc.resolution_code is ResolutionCode.CONDITION_CLEARED
    assert exc.resolution_actor is ActorType.SYSTEM
    assert exc.resolved_at == T0 + 3 * H
    assert exc.resolved_by is None
    assert event_types(db, exc)[-1] is ExceptionEventType.AUTO_RESOLVED


def test_only_rules_that_ran_can_auto_resolve(
    db: Session, tenant: Tenant, product: Product
) -> None:
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    _ship(db, tenant, order, product, T0 + 2 * H)

    partial = evaluate(db, tenant, T0 + 3 * H, rule_ids=["INV-OVERSOLD@1", "INV-BELOW-ROP@1"])

    assert partial.rules == ["INV-OVERSOLD@1", "INV-BELOW-ROP@1"]
    assert partial.counts["resolved"] == 0
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.status is ExceptionStatus.OPEN
    # Active exceptions of rules that did not run still get a fresh priority.
    assert exc.priority_breakdown["as_of"] == (T0 + 3 * H).isoformat()

    full = evaluate(db, tenant, T0 + 4 * H, rule_ids=["ORD-OVERDUE@1"])
    assert full.counts["resolved"] == 1


# --- R4: verification of manual resolutions ------------------------------------------------------


def _resolve_manually(
    db: Session, tenant: Tenant, exc: OperationalException, user: User, at: datetime
) -> None:
    ctx = _ctx(db, tenant, user)
    service.start(db, ctx, exc.id, expected_version=None, now=at - timedelta(minutes=5))
    service.resolve(
        db,
        ctx,
        exc.id,
        resolution_code=ResolutionCode.ORDER_FULFILLED,
        resolution_note="Collected by carrier, tracking in source.",
        expected_version=None,
        now=at,
    )


def test_r4_absent_after_manual_resolution_is_verified(
    db: Session, tenant: Tenant, product: Product
) -> None:
    staff = create_user(db, tenant, Role.STAFF)
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    exc = one_exception(db, tenant, OVERDUE, order.id)
    _resolve_manually(db, tenant, exc, staff, T0 + 2 * H)
    _ship(db, tenant, order, product, T0 + 2 * H)

    run = evaluate(db, tenant, T0 + 3 * H)

    assert run.counts["verified"] == 1
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.status is ExceptionStatus.RESOLVED
    assert exc.verified_at == T0 + 3 * H
    assert event_types(db, exc)[-1] is ExceptionEventType.VERIFIED

    again = evaluate(db, tenant, T0 + 4 * H)
    assert again.counts["verified"] == 0  # verified once only


def test_r4_present_before_fresh_data_or_grace_period_waits_without_event(
    db: Session, tenant: Tenant, product: Product
) -> None:
    """Orchestrator decision: no VERIFICATION_FAILED until an import completed after the
    resolution or VERIFICATION_GRACE_HOURS (24) have passed."""
    staff = create_user(db, tenant, Role.STAFF)
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    exc = one_exception(db, tenant, OVERDUE, order.id)
    _resolve_manually(db, tenant, exc, staff, T0 + 2 * H)
    events_before = event_types(db, exc)

    run = evaluate(db, tenant, T0 + 3 * H)

    assert run.counts["reopened"] == 0
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.status is ExceptionStatus.RESOLVED
    assert exc.verified_at is None
    assert event_types(db, exc) == events_before

    grace = evaluate(db, tenant, T0 + 2 * H + timedelta(hours=VERIFICATION_GRACE_HOURS))

    assert grace.counts["reopened"] == 1
    exc = one_exception(db, tenant, OVERDUE, order.id)
    assert exc.status is ExceptionStatus.REOPENED
    reopened = db.scalars(
        select(ExceptionEvent).where(
            ExceptionEvent.exception_id == exc.id,
            ExceptionEvent.event_type == ExceptionEventType.REOPENED,
        )
    ).one()
    assert reopened.payload["reason"] == "VERIFICATION_FAILED"
    assert reopened.payload["previous_resolution"]["resolution_code"] == "ORDER_FULFILLED"
    assert exc.reopen_count == 1
    assert exc.resolution_code is None
    assert exc.resolved_at is None
    assert exc.assignee_id == staff.id  # assignment is an attribute, not a state


def test_r4_present_after_a_completed_import_reopens_with_verification_failed(
    db: Session, tenant: Tenant, product: Product
) -> None:
    staff = create_user(db, tenant, Role.STAFF)
    order = _overdue_order(db, tenant, product)
    evaluate(db, tenant, T0 + 1 * H)
    exc = one_exception(db, tenant, OVERDUE, order.id)
    _resolve_manually(db, tenant, exc, staff, T0 + 2 * H)
    db.add(
        DataImport(
            store_id=tenant.store.id,
            import_type=ImportType.ORDERS,
            status=ImportStatus.COMPLETED,
            original_filename="orders.csv",
            file_sha256="0" * 64,
            size_bytes=10,
            applied_at=T0 + 2 * H + timedelta(minutes=5),
        )
    )

    run = evaluate(db, tenant, T0 + 3 * H)

    assert run.counts["reopened"] == 1
    assert one_exception(db, tenant, OVERDUE, order.id).status is ExceptionStatus.REOPENED


# --- R5 / R6: recurrence -------------------------------------------------------------------------


def _resolved_by_system(db: Session, tenant: Tenant) -> tuple[Product, OperationalException]:
    item = make_product(db, tenant, "KH-BOWL-01", reorder_point=0)
    evaluate(db, tenant, T0)  # out of stock
    adjust_stock(db, tenant, item, MovementType.RECEIPT, 5, T0 + 1 * H)
    evaluate(db, tenant, T0 + 2 * H)  # auto-resolved
    exc = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    assert exc.resolution_code is ResolutionCode.CONDITION_CLEARED
    return item, exc


def test_r5_recurrence_within_window_reopens_and_restarts_the_due_date(
    db: Session, tenant: Tenant
) -> None:
    item, _ = _resolved_by_system(db, tenant)
    adjust_stock(db, tenant, item, MovementType.DAMAGE, 5, T0 + 10 * H)

    run = evaluate(db, tenant, T0 + 2 * H + 72 * H)  # exactly at the end of the window

    assert run.counts["reopened"] == 1
    (exc,) = exceptions_for(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    assert exc.status is ExceptionStatus.REOPENED
    assert exc.due_at == T0 + 74 * H + 72 * H  # reopen time + MEDIUM 72 h
    reopened = db.scalars(
        select(ExceptionEvent).where(
            ExceptionEvent.exception_id == exc.id,
            ExceptionEvent.event_type == ExceptionEventType.REOPENED,
        )
    ).one()
    assert reopened.payload["reason"] == "RECURRED_WITHIN_WINDOW"
    assert reopened.payload["due_date_changed"]["to"] == (T0 + 146 * H).isoformat()


def test_r6_recurrence_after_window_creates_a_linked_new_occurrence(
    db: Session, tenant: Tenant
) -> None:
    item, old = _resolved_by_system(db, tenant)
    adjust_stock(db, tenant, item, MovementType.DAMAGE, 5, T0 + 10 * H)

    run = evaluate(db, tenant, T0 + 2 * H + 72 * H + timedelta(seconds=1))

    assert run.counts["created"] == 1
    old_row, new = exceptions_for(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    assert old_row.id == old.id
    assert old_row.status is ExceptionStatus.RESOLVED
    assert new.status is ExceptionStatus.OPEN
    assert new.previous_occurrence_id == old.id
    assert new.reference != old.reference


# --- R7 / R8: dismissed ---------------------------------------------------------------------------


def test_r7_dismissed_condition_present_updates_last_detected_only_and_absent_sets_cleared(
    db: Session, tenant: Tenant
) -> None:
    manager = create_user(db, tenant, Role.MANAGER)
    item = make_product(db, tenant, "KH-BOWL-01", reorder_point=0)
    evaluate(db, tenant, T0)
    exc = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    service.dismiss(
        db,
        _ctx(db, tenant, manager),
        exc.id,
        dismissal_reason=DismissalReason.ACCEPTED_RISK,
        note="Seasonal item, will not be restocked.",
        expected_version=None,
        now=T0 + 1 * H,
    )
    events_before = event_types(db, exc)
    version_before = one_exception(
        db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id
    ).version

    run = evaluate(db, tenant, T0 + 2 * H)

    assert run.counts["unchanged"] == 1
    assert run.counts["created"] == 0
    exc = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    assert exc.status is ExceptionStatus.DISMISSED
    assert exc.last_detected_at == T0 + 2 * H
    assert exc.condition_cleared_at is None
    assert event_types(db, exc) == events_before
    assert exc.version == version_before

    adjust_stock(db, tenant, item, MovementType.RECEIPT, 3, T0 + 3 * H)
    evaluate(db, tenant, T0 + 4 * H)

    exc = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    assert exc.status is ExceptionStatus.DISMISSED
    assert exc.condition_cleared_at == T0 + 4 * H
    assert event_types(db, exc) == events_before


def test_r8_dismissed_and_cleared_condition_detected_again_creates_new_occurrence(
    db: Session, tenant: Tenant
) -> None:
    manager = create_user(db, tenant, Role.MANAGER)
    item = make_product(db, tenant, "KH-BOWL-01", reorder_point=0)
    evaluate(db, tenant, T0)
    old = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    service.dismiss(
        db,
        _ctx(db, tenant, manager),
        old.id,
        dismissal_reason=DismissalReason.FALSE_POSITIVE,
        note="Stock count was missing from the export.",
        expected_version=None,
        now=T0 + 1 * H,
    )
    adjust_stock(db, tenant, item, MovementType.RECEIPT, 3, T0 + 2 * H)
    evaluate(db, tenant, T0 + 3 * H)  # condition_cleared_at set
    adjust_stock(db, tenant, item, MovementType.DAMAGE, 3, T0 + 4 * H)

    run = evaluate(db, tenant, T0 + 5 * H)

    assert run.counts["created"] == 1
    first, second = exceptions_for(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, item.id)
    assert first.status is ExceptionStatus.DISMISSED
    assert second.status is ExceptionStatus.OPEN
    assert second.previous_occurrence_id == first.id


# --- supersede (BR-401) ---------------------------------------------------------------------------


def test_more_severe_inventory_condition_supersedes_and_carries_the_assignee_over(
    db: Session, tenant: Tenant
) -> None:
    staff = create_user(db, tenant, Role.STAFF)
    knife = make_product(db, tenant, "KHK-CHF-20", reorder_point=8)
    set_stock(db, tenant, knife, 5, T0 - 1 * H)
    evaluate(db, tenant, T0)
    below = one_exception(db, tenant, ExceptionType.INVENTORY_BELOW_REORDER_POINT, knife.id)
    service.start(db, _ctx(db, tenant, staff), below.id, expected_version=None, now=T0 + 1 * H)
    make_order(
        db,
        tenant,
        OrderSpec("KHK-2001", OrderStatus.PAID, [LineSpec(knife, 5)], paid_at=T0 + 2 * H),
    )

    run = evaluate(db, tenant, T0 + 3 * H)

    assert run.counts["superseded"] == 1
    assert run.counts["created"] == 1
    old = one_exception(db, tenant, ExceptionType.INVENTORY_BELOW_REORDER_POINT, knife.id)
    new = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, knife.id)
    assert old.status is ExceptionStatus.RESOLVED
    assert old.resolution_code is ResolutionCode.SUPERSEDED
    assert old.superseded_by_id == new.id
    assert event_types(db, old)[-1] is ExceptionEventType.SUPERSEDED
    assert new.status is ExceptionStatus.OPEN
    assert new.assignee_id == staff.id
    assert event_types(db, new) == [ExceptionEventType.DETECTED, ExceptionEventType.ASSIGNED]
    assigned = db.scalars(
        select(ExceptionEvent).where(
            ExceptionEvent.exception_id == new.id,
            ExceptionEvent.event_type == ExceptionEventType.ASSIGNED,
        )
    ).one()
    assert assigned.actor_type is ActorType.SYSTEM
    assert assigned.payload["carried_over_from_id"] == str(old.id)
    assert db.scalars(
        select(ExceptionAssignment.assignee_id).where(ExceptionAssignment.exception_id == new.id)
    ).all() == [staff.id]


def test_br402a_negative_on_hand_supersedes_the_active_inventory_exception(
    db: Session, tenant: Tenant
) -> None:
    staff = create_user(db, tenant, Role.STAFF)
    kettle = make_product(db, tenant, "KHK-KTL-30", reorder_point=8)
    set_stock(db, tenant, kettle, 5, T0 - 1 * H)
    evaluate(db, tenant, T0)
    below = one_exception(db, tenant, ExceptionType.INVENTORY_BELOW_REORDER_POINT, kettle.id)
    service.start(db, _ctx(db, tenant, staff), below.id, expected_version=None, now=T0 + 1 * H)
    adjust_stock(db, tenant, kettle, MovementType.DAMAGE, 9, T0 + 2 * H)  # on_hand 5 -> -4

    run = evaluate(db, tenant, T0 + 3 * H)

    assert run.counts["superseded"] == 1
    old = one_exception(db, tenant, ExceptionType.INVENTORY_BELOW_REORDER_POINT, kettle.id)
    data_issue = one_exception(db, tenant, ExceptionType.DATA_NEGATIVE_ON_HAND, kettle.id)
    assert old.resolution_code is ResolutionCode.SUPERSEDED  # not CONDITION_CLEARED
    assert old.superseded_by_id == data_issue.id
    assert data_issue.assignee_id == staff.id


def test_br402a_negative_on_hand_supersedes_oversold_until_a_count_corrects_it(
    db: Session, tenant: Tenant
) -> None:
    """BR-402a: once on_hand < 0, INVENTORY_OVERSOLD no longer fires. The active one is SUPERSEDED
    by DATA_NEGATIVE_ON_HAND (not CONDITION_CLEARED). A cycle count clears the data issue and the
    inventory rules apply again."""
    pan = make_product(db, tenant, "KH-PAN-30", reorder_point=4)
    set_stock(db, tenant, pan, 2, T0 - 2 * H)
    make_order(
        db, tenant, OrderSpec("KHK-5001", OrderStatus.PAID, [LineSpec(pan, 3)], paid_at=T0 - H)
    )
    evaluate(db, tenant, T0)
    oversold = one_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, pan.id)
    assert oversold.status in ACTIVE_STATUSES
    adjust_stock(db, tenant, pan, MovementType.DAMAGE, 3, T0 + H)  # on_hand 2 -> -1, reserved 3

    run = evaluate(db, tenant, T0 + 2 * H)

    assert run.counts["superseded"] == 1
    oversold = one_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, pan.id)
    data_issue = one_exception(db, tenant, ExceptionType.DATA_NEGATIVE_ON_HAND, pan.id)
    assert oversold.resolution_code is ResolutionCode.SUPERSEDED
    assert oversold.superseded_by_id == data_issue.id
    rows = exceptions_for(db, tenant, entity_id=pan.id)
    assert [e.exception_type for e in rows if e.status in ACTIVE_STATUSES] == [
        ExceptionType.DATA_NEGATIVE_ON_HAND
    ]

    set_stock(db, tenant, pan, 6, T0 + 3 * H)  # counted 6: available 3, below reorder point 4
    evaluate(db, tenant, T0 + 4 * H)

    data_issue = one_exception(db, tenant, ExceptionType.DATA_NEGATIVE_ON_HAND, pan.id)
    assert data_issue.resolution_code is ResolutionCode.CONDITION_CLEARED
    below = one_exception(db, tenant, ExceptionType.INVENTORY_BELOW_REORDER_POINT, pan.id)
    assert below.status is ExceptionStatus.OPEN


def test_overdue_supersedes_stalled_for_the_same_order(
    db: Session, tenant: Tenant, product: Product
) -> None:
    order = make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-3001",
            OrderStatus.PAID,
            [LineSpec(product, 1)],
            paid_at=T0,
            ship_by=T0 + 20 * H,
        ),
    )
    evaluate(db, tenant, T0 + 13 * H)
    stalled = one_exception(db, tenant, ExceptionType.ORDER_STALLED_AFTER_PAYMENT, order.id)
    assert stalled.status is ExceptionStatus.OPEN

    run = evaluate(db, tenant, T0 + 21 * H)

    assert run.counts["superseded"] == 1
    stalled = one_exception(db, tenant, ExceptionType.ORDER_STALLED_AFTER_PAYMENT, order.id)
    overdue = one_exception(db, tenant, OVERDUE, order.id)
    assert stalled.resolution_code is ResolutionCode.SUPERSEDED
    assert stalled.superseded_by_id == overdue.id


def test_superseded_is_final_and_a_returning_condition_is_a_new_occurrence(
    db: Session, tenant: Tenant
) -> None:
    """Orchestrator decision: SUPERSEDED is never reopened. The returning condition is a new
    occurrence; its assignee comes from the most recent exception of the supersede chain."""
    staff = create_user(db, tenant, Role.STAFF)
    manager = create_user(db, tenant, Role.MANAGER)
    pan = make_product(db, tenant, "KH-PAN-28", reorder_point=0)
    set_stock(db, tenant, pan, 2, T0 - 1 * H)
    make_order(db, tenant, OrderSpec("KHK-4001", OrderStatus.PAID, [LineSpec(pan, 2)], paid_at=T0))
    evaluate(db, tenant, T0 + 1 * H)  # out of stock
    oos = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, pan.id)
    service.start(db, _ctx(db, tenant, staff), oos.id, expected_version=None, now=T0 + 1 * H)
    late = make_order(
        db,
        tenant,
        OrderSpec("KHK-4002", OrderStatus.PAID, [LineSpec(pan, 1)], paid_at=T0 + 2 * H),
    )
    evaluate(db, tenant, T0 + 3 * H)  # oversold supersedes out of stock
    oversold = one_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, pan.id)
    assert oversold.assignee_id == staff.id
    service.assign(
        db,
        _ctx(db, tenant, manager),
        oversold.id,
        assignee_id=manager.id,
        expected_version=None,
        now=T0 + 4 * H,
    )
    make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-4002",
            OrderStatus.CANCELLED,
            [LineSpec(pan, 1)],
            placed_at=late.placed_at,
            cancelled_at=T0 + 5 * H,
        ),
    )

    run = evaluate(db, tenant, T0 + 6 * H)  # back to out of stock, inside the 72 h window

    assert run.counts["reopened"] == 0
    assert run.counts["created"] == 1
    old_oos, new_oos = exceptions_for(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, pan.id)
    assert old_oos.id == oos.id
    assert old_oos.status is ExceptionStatus.RESOLVED
    assert old_oos.resolution_code is ResolutionCode.SUPERSEDED
    assert new_oos.status is ExceptionStatus.OPEN
    assert new_oos.previous_occurrence_id == oos.id
    assert new_oos.assignee_id == manager.id  # from the end of the chain (the oversold one)
    oversold = one_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, pan.id)
    assert oversold.resolution_code is ResolutionCode.CONDITION_CLEARED


def test_carry_over_skips_assignees_who_can_no_longer_work_exceptions(
    db: Session, tenant: Tenant
) -> None:
    staff = create_user(db, tenant, Role.STAFF)
    knife = make_product(db, tenant, "KHK-CHF-20", reorder_point=8)
    set_stock(db, tenant, knife, 5, T0 - 1 * H)
    evaluate(db, tenant, T0)
    below = one_exception(db, tenant, ExceptionType.INVENTORY_BELOW_REORDER_POINT, knife.id)
    service.start(db, _ctx(db, tenant, staff), below.id, expected_version=None, now=T0 + 1 * H)
    staff.is_active = False
    db.commit()
    make_order(
        db,
        tenant,
        OrderSpec("KHK-2001", OrderStatus.PAID, [LineSpec(knife, 5)], paid_at=T0 + 2 * H),
    )

    evaluate(db, tenant, T0 + 3 * H)

    new = one_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, knife.id)
    assert new.assignee_id is None
