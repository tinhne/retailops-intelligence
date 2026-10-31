"""Scheduled evaluation worker (T-055, ADR-0009)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import utcnow
from app.domains.exceptions.models import EvaluationRun, EvaluationStatus, EvaluationTrigger
from app.workers.scheduler import due_store_ids, run_once
from tests.factories import create_tenant

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def _run(db: Session, store_id: object, started_at: datetime) -> None:
    db.add(
        EvaluationRun(
            store_id=store_id,
            trigger=EvaluationTrigger.IMPORT,
            status=EvaluationStatus.SUCCEEDED,
            as_of=started_at,
            rules=[],
            counts={},
            started_at=started_at,
            finished_at=started_at,
        )
    )
    db.commit()


def test_store_is_due_without_runs_or_after_its_interval(db: Session) -> None:
    never = create_tenant(db, "never")
    fresh = create_tenant(db, "fresh")
    stale = create_tenant(db, "stale")
    _run(db, fresh.store.id, NOW - timedelta(minutes=5))  # any trigger resets the clock
    _run(db, stale.store.id, NOW - timedelta(minutes=15))  # default interval: 15 minutes

    due = due_store_ids(db, NOW)

    assert due == [never.store.id, stale.store.id]  # never-evaluated stores first


def test_run_once_records_scheduled_runs_and_is_quiet_when_nothing_is_due(
    db: Session, session_factory: sessionmaker[Session]
) -> None:
    tenant = create_tenant(db)

    # Run records use the wall clock for started_at, so this test uses real time.
    first = run_once(session_factory)
    second = run_once(session_factory, clock=lambda: utcnow() + timedelta(minutes=1))

    assert [r.store_id for r in first] == [tenant.store.id]
    assert first[0].trigger is EvaluationTrigger.SCHEDULED
    assert first[0].status is EvaluationStatus.SUCCEEDED
    assert second == []
    assert len(db.scalars(select(EvaluationRun)).all()) == 1
