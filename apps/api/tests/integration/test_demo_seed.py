"""Demo dataset generator and reset job (T-056, T-094): scenarios, history and consistency."""

import uuid
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.demo import __main__ as demo_cli
from app.demo.build import build_demo, reset_lock
from app.demo.seed import DEMO_ORG_SLUG, DemoSeedRefusedError, seed_demo
from app.domains.catalog.models import Product
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    EvaluationRun,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionNote,
    ExceptionStatus,
    ExceptionType,
    OperationalException,
)
from app.domains.identity.models import Membership, Organization, User
from app.domains.identity.permissions import Role
from app.domains.imports.models import DataImport
from app.domains.inventory import service as inventory
from tests.conftest import TEST_DATABASE_URL
from tests.factories import create_tenant

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)


def _balance(db: Session, store_id: object, sku: str) -> tuple[int, int, int]:
    product = db.scalars(
        select(Product).where(Product.store_id == store_id, Product.sku == sku)
    ).one()
    balance = inventory.get_balance(db, product.store_id, product.id)
    return balance.on_hand, balance.reserved, product.reorder_point


def test_seed_is_consistent_and_engineers_every_inventory_scenario(db: Session) -> None:
    summary = seed_demo(db, now=NOW, seed=7)
    db.commit()

    assert summary.orders > 1000
    assert inventory.reconcile(db, summary.store_id) == []  # BR-104: ledger == balances
    scenarios = summary.scenarios
    for sku in scenarios["INVENTORY_OVERSOLD"]:
        on_hand, reserved, _ = _balance(db, summary.store_id, sku)
        assert on_hand >= 0
        assert reserved > on_hand  # BR-402a: oversold always has committed demand
    (oos,) = scenarios["INVENTORY_OUT_OF_STOCK"]
    on_hand, reserved, _ = _balance(db, summary.store_id, oos)
    assert on_hand - reserved == 0
    for sku in scenarios["INVENTORY_BELOW_REORDER_POINT"]:
        on_hand, reserved, rop = _balance(db, summary.store_id, sku)
        assert 0 < on_hand - reserved <= rop
    (negative,) = scenarios["DATA_NEGATIVE_ON_HAND"]
    assert _balance(db, summary.store_id, negative)[0] < 0
    for key in (
        "ORDER_FULFILLMENT_OVERDUE",
        "ORDER_STALLED_AFTER_PAYMENT",
        "ORDER_REFUND_PENDING",
        "DATA_ORDER_TOTAL_MISMATCH",
    ):
        assert scenarios[key], key


def test_reseeding_replaces_the_demo_org_and_keeps_viewer_read_only(db: Session) -> None:
    first = seed_demo(db, now=NOW, seed=7)
    db.commit()
    second = seed_demo(db, now=NOW, seed=7)
    db.commit()

    assert first.organization_id != second.organization_id
    roles = db.scalars(
        select(Membership.role).where(Membership.organization_id == second.organization_id)
    ).all()
    assert roles.count(Role.VIEWER) == 1
    assert Role.OWNER in roles


# --- exception history and the reset job (T-056, T-094) ----------------------------------------

# Snapshot for the default seed at NOW. A deliberate change to the seed or the history script
# updates these numbers in the same commit.
HISTORY_SNAPSHOT: dict[str, dict[str, int]] = {
    "exceptions_by_status": {
        "ACKNOWLEDGED": 1,
        "DISMISSED": 1,
        "IN_PROGRESS": 1,
        "OPEN": 12,
        "REOPENED": 1,
        "RESOLVED": 2,
    },
    "exceptions_by_type": {
        "DATA_NEGATIVE_ON_HAND": 1,
        "DATA_ORDER_TOTAL_MISMATCH": 2,
        "INVENTORY_BELOW_REORDER_POINT": 3,
        "INVENTORY_OUT_OF_STOCK": 1,
        "INVENTORY_OVERSELL_RISK": 1,
        "INVENTORY_OVERSOLD": 2,
        "ORDER_FULFILLMENT_OVERDUE": 3,
        "ORDER_REFUND_PENDING": 2,
        "ORDER_STALLED_AFTER_PAYMENT": 3,
    },
    "events_by_type": {
        "ASSIGNED": 6,
        "DETECTED": 18,
        "NOTE_ADDED": 3,
        "REOPENED": 1,
        "STATUS_CHANGED": 9,
        "VERIFIED": 2,
    },
    "imports_by_status": {"COMPLETED": 2},
    "evaluation_runs_by_trigger": {"IMPORT": 2, "SCHEDULED": 2},
    "work": {"assigned_active": 4, "verified": 2, "notes": 3},
}


def _counter(values: Iterable[object]) -> dict[str, int]:
    return dict(sorted(Counter(str(getattr(v, "value", v)) for v in values).items()))


def _history_snapshot(db: Session, store_id: uuid.UUID) -> dict[str, dict[str, int]]:
    exceptions = db.scalars(
        select(OperationalException).where(OperationalException.store_id == store_id)
    ).all()
    events = db.scalars(
        select(ExceptionEvent.event_type).where(ExceptionEvent.store_id == store_id)
    ).all()
    imports = db.scalars(select(DataImport.status).where(DataImport.store_id == store_id)).all()
    runs = db.scalars(select(EvaluationRun.trigger).where(EvaluationRun.store_id == store_id)).all()
    notes = db.scalar(
        select(func.count()).select_from(ExceptionNote).where(ExceptionNote.store_id == store_id)
    )
    return {
        "exceptions_by_status": _counter(e.status for e in exceptions),
        "exceptions_by_type": _counter(e.exception_type for e in exceptions),
        "events_by_type": _counter(events),
        "imports_by_status": _counter(imports),
        "evaluation_runs_by_trigger": _counter(runs),
        "work": {
            "assigned_active": sum(
                1 for e in exceptions if e.assignee_id and e.status in ACTIVE_STATUSES
            ),
            "verified": sum(1 for e in exceptions if e.verified_at is not None),
            "notes": notes or 0,
        },
    }


def _story(db: Session, store_id: uuid.UUID) -> list[tuple[object, ...]]:
    """Per exception: reference, type, status, assignee and priority."""
    rows = db.execute(
        select(
            OperationalException.reference,
            OperationalException.exception_type,
            OperationalException.status,
            User.email,
            OperationalException.priority_score,
        )
        .outerjoin(User, User.id == OperationalException.assignee_id)
        .where(OperationalException.store_id == store_id)
        .order_by(OperationalException.reference)
    ).all()
    return [tuple(row) for row in rows]


def test_demo_build_produces_the_history_snapshot_deterministically(db: Session) -> None:
    first = build_demo(db, now=NOW)
    first_snapshot = _history_snapshot(db, first.summary.store_id)
    first_story = _story(db, first.summary.store_id)
    second = build_demo(db, now=NOW)
    store_id = second.summary.store_id

    assert first_snapshot == HISTORY_SNAPSHOT
    assert _history_snapshot(db, store_id) == HISTORY_SNAPSHOT
    assert _story(db, store_id) == first_story  # same seed and now: the same story
    assert second.history.imports == [
        "inventory_adjustments_rush_delivery.csv",
        "orders_export_morning.csv",
    ]
    # The rush delivery verifies the restock. The orders export verifies the released order and
    # reopens the refund that still shows as paid (STATE_MACHINES §3.3, verification).
    assert [(e["verified"], e["reopened"]) for e in second.history.evaluations] == [(1, 0), (1, 1)]
    reopened = db.scalars(
        select(OperationalException).where(
            OperationalException.store_id == store_id,
            OperationalException.status == ExceptionStatus.REOPENED,
        )
    ).one()
    assert reopened.exception_type is ExceptionType.ORDER_REFUND_PENDING
    payload = db.scalars(
        select(ExceptionEvent.payload).where(
            ExceptionEvent.exception_id == reopened.id,
            ExceptionEvent.event_type == ExceptionEventType.REOPENED,
        )
    ).one()
    assert payload["reason"] == "VERIFICATION_FAILED"
    # The team history happened before "now", and the ledger still reconciles (BR-104).
    latest = db.scalar(
        select(func.max(ExceptionEvent.occurred_at)).where(ExceptionEvent.store_id == store_id)
    )
    assert latest is not None
    assert latest <= NOW
    assert inventory.reconcile(db, store_id) == []


def test_demo_history_holds_for_another_seed(db: Session) -> None:
    result = build_demo(db, now=NOW, seed=7)

    statuses = _history_snapshot(db, result.summary.store_id)["exceptions_by_status"]
    for status in ("ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "REOPENED", "DISMISSED"):
        assert statuses.get(status, 0) >= 1, status


def test_seed_refuses_to_purge_an_organization_that_is_not_a_demo(db: Session) -> None:
    real = create_tenant(db, DEMO_ORG_SLUG, is_demo=False)

    with pytest.raises(DemoSeedRefusedError):
        seed_demo(db, now=NOW, seed=7)
    db.rollback()

    assert db.get(Organization, real.organization.id) is not None


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point ``python -m app.demo`` at the test database without replacing the log handlers."""
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.delenv("DEMO_STAFF_PASSWORD", raising=False)
    monkeypatch.setattr(demo_cli, "configure_logging", lambda _level: None)
    caches = (get_settings, get_engine, get_session_factory)
    for cache in caches:
        cache.cache_clear()
    yield
    get_engine().dispose()
    for cache in caches:
        cache.cache_clear()


@pytest.mark.usefixtures("cli_env")
def test_reset_command_seeds_when_missing_and_never_runs_twice_at_once(db: Session) -> None:
    def demo_org_id() -> uuid.UUID | None:
        return db.scalar(select(Organization.id).where(Organization.slug == DEMO_ORG_SLUG))

    assert demo_cli.main(["--if-missing"]) == 0
    org_id = demo_org_id()
    assert org_id is not None

    assert demo_cli.main(["--if-missing"]) == 0  # already seeded: nothing is regenerated
    assert demo_org_id() == org_id

    with reset_lock(get_engine()) as held:
        assert held
        assert demo_cli.main([]) == demo_cli.EXIT_LOCKED  # a concurrent reset changes nothing
    assert demo_org_id() == org_id


@pytest.mark.usefixtures("cli_env")
def test_reset_command_refuses_staff_passwords_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("DEMO_STAFF_PASSWORD", "published-password")
    get_settings.cache_clear()

    assert demo_cli.main([]) == 2
