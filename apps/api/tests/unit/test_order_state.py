"""Order lifecycle (STATE_MACHINES.md §1)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domains.orders.models import FulfillmentStatus as F
from app.domains.orders.models import OrderStatus as S
from app.domains.orders.models import PaymentStatus as P
from app.domains.orders.state import (
    AXES,
    TRANSITIONS,
    DemandClass,
    OrderTimestamps,
    axis_errors,
    can_transition,
    default_fulfillment,
    demand_class,
    path_to,
    timestamp_issues,
    transition_error,
)

T0 = datetime(2026, 10, 1, 12, tzinfo=UTC)


def test_transition_table_covers_every_status() -> None:
    assert set(TRANSITIONS) == set(S)
    assert set(AXES) == set(S)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.CREATED, S.PAYMENT_PENDING),
        (S.PAYMENT_PENDING, S.PAID),
        (S.PAYMENT_FAILED, S.PAYMENT_PENDING),
        (S.PAID, S.PROCESSING),
        (S.READY_TO_SHIP, S.SHIPPED),
        (S.SHIPPED, S.RETURNED),
        (S.DELIVERED, S.REFUNDED),
        (S.RETURN_REQUESTED, S.DELIVERED),
        (S.CANCELLED, S.REFUNDED),
    ],
)
def test_allowed_direct_transitions(current: S, target: S) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.DELIVERED, S.PAID),
        (S.SHIPPED, S.CANCELLED),
        (S.REFUNDED, S.DELIVERED),
        (S.CREATED, S.PAID),
        (S.CANCELLED, S.SHIPPED),
    ],
)
def test_disallowed_direct_transitions(current: S, target: S) -> None:
    assert not can_transition(current, target)


def test_reachability_records_skipped_states_for_import_sync() -> None:
    assert path_to(S.PAID, S.SHIPPED) == [S.PAID, S.PROCESSING, S.READY_TO_SHIP, S.SHIPPED]
    assert path_to(S.PAID, S.PAID) == [S.PAID]


@pytest.mark.parametrize(
    ("current", "target"), [(S.DELIVERED, S.PAID), (S.CANCELLED, S.SHIPPED), (S.REFUNDED, S.PAID)]
)
def test_unreachable_targets_are_rejected(current: S, target: S) -> None:
    assert path_to(current, target) is None
    assert transition_error(current, P.PAID, target) is not None


def test_refund_after_cancellation_requires_prior_payment() -> None:
    assert transition_error(S.CANCELLED, P.PAID, S.REFUNDED) is None
    assert transition_error(S.CANCELLED, P.PENDING, S.REFUNDED) is not None


def test_axis_matrix_rejects_invalid_combinations() -> None:
    assert axis_errors(S.SHIPPED, P.PAID, F.SHIPPED) == []
    assert axis_errors(S.CANCELLED, P.PAID, F.UNFULFILLED) == []  # refund owed, still valid
    assert len(axis_errors(S.SHIPPED, P.FAILED, F.SHIPPED)) == 1
    assert len(axis_errors(S.PAID, P.PENDING, F.DELIVERED)) == 2


def test_default_fulfillment_is_derived_except_for_refunded() -> None:
    assert default_fulfillment(S.PROCESSING) is F.IN_PROGRESS
    assert default_fulfillment(S.CANCELLED) is F.UNFULFILLED
    assert default_fulfillment(S.REFUNDED) is None


def test_required_timestamps_and_sequence() -> None:
    missing = timestamp_issues(
        S.SHIPPED,
        P.PAID,
        F.SHIPPED,
        OrderTimestamps(T0, paid_at=None, shipped_at=None, delivered_at=None, cancelled_at=None),
    )
    assert {i.field for i in missing} == {"paid_at", "shipped_at"}

    out_of_order = timestamp_issues(
        S.DELIVERED,
        P.PAID,
        F.DELIVERED,
        OrderTimestamps(
            T0,
            paid_at=T0 + timedelta(hours=1),
            shipped_at=T0,  # before paid_at
            delivered_at=T0 + timedelta(days=2),
            cancelled_at=None,
        ),
    )
    assert [(i.field, i.code) for i in out_of_order] == [("shipped_at", "ORDER_TIMESTAMP_SEQUENCE")]


@pytest.mark.parametrize(
    ("status", "fulfillment", "expected"),
    [
        (S.PAYMENT_PENDING, F.UNFULFILLED, DemandClass.PENDING),
        (S.PAID, F.UNFULFILLED, DemandClass.COMMITTED),
        (S.READY_TO_SHIP, F.IN_PROGRESS, DemandClass.COMMITTED),
        (S.DELIVERED, F.DELIVERED, DemandClass.FULFILLED),
        (S.REFUNDED, F.RETURNED, DemandClass.FULFILLED),
        (S.REFUNDED, F.UNFULFILLED, DemandClass.NONE),
        (S.CANCELLED, F.UNFULFILLED, DemandClass.NONE),
        (S.PAYMENT_FAILED, F.UNFULFILLED, DemandClass.NONE),
    ],
)
def test_demand_classification_drives_reservations(
    status: S, fulfillment: F, expected: DemandClass
) -> None:
    assert demand_class(status, fulfillment) is expected
