"""Fictional Vietnamese sample shops: valid input for the import pipeline, engineered outcomes."""

import csv
import io
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.demo.sample_stores import IMPORT_ORDER, build_store, load_store
from app.demo.vn_store_data import STORES
from app.domains.exceptions.models import ACTIVE_STATUSES, ExceptionType, OperationalException
from app.domains.identity.models import Organization
from app.domains.orders.models import FulfillmentStatus, OrderStatus, PaymentStatus
from app.domains.orders.state import OrderTimestamps, axis_errors, timestamp_issues

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 1, 5, 0, tzinfo=UTC)


def _ts(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@pytest.mark.parametrize("store", STORES, ids=lambda s: s.slug)
def test_every_template_order_respects_the_order_state_rules(store: object) -> None:
    data = build_store(store, NOW)  # type: ignore[arg-type]
    assert list(data.files) == list(IMPORT_ORDER)
    rows = list(csv.DictReader(io.StringIO(data.files["orders"])))
    assert len(rows) == data.order_count
    for row in rows:
        status = OrderStatus(row["status"])
        payment = PaymentStatus(row["payment_status"])
        fulfillment = FulfillmentStatus(row["fulfillment_status"])
        assert axis_errors(status, payment, fulfillment) == [], row["order_number"]
        stamps = OrderTimestamps(
            placed_at=_ts(row["placed_at"]),  # type: ignore[arg-type]
            paid_at=_ts(row["paid_at"]),
            shipped_at=_ts(row["shipped_at"]),
            delivered_at=_ts(row["delivered_at"]),
            cancelled_at=_ts(row["cancelled_at"]),
        )
        assert timestamp_issues(status, payment, fulfillment, stamps) == [], row["order_number"]
        assert row["currency"] == "VND"
        assert row["placed_at"].endswith("+07:00")


def test_loading_a_shop_through_the_import_pipeline_yields_exactly_its_scenarios(
    db: Session,
) -> None:
    store = next(s for s in STORES if s.slug == "len-xanh-handmade")

    loaded = load_store(db, store, NOW, replace=False, owner_password=None, clock=lambda: NOW)

    assert loaded is not None
    org = db.scalars(select(Organization).where(Organization.slug == store.slug)).one()
    assert org.is_demo is False
    active = dict(
        db.execute(
            select(OperationalException.exception_type, func.count())
            .where(OperationalException.status.in_(ACTIVE_STATUSES))
            .group_by(OperationalException.exception_type)
        ).all()
    )
    expected = build_store(store, NOW).scenarios
    assert {k.value: v for k, v in active.items()} == {k: len(v) for k, v in expected.items()}
    assert ExceptionType.INVENTORY_OVERSOLD in active
    # A second load without --replace leaves the shop alone.
    assert load_store(db, store, NOW, replace=False, owner_password=None, clock=lambda: NOW) is None
