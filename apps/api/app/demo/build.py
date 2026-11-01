"""Build (or rebuild) the complete demo organization: dataset, evaluations and team history.

This is the demo reset job (T-094, ADR-0011). It is the only code path allowed to delete rows from
append-only tables, and ``seed_demo`` refuses to touch an organization that is not flagged
``is_demo``. A reset signs out every current demo visitor, because the demo accounts are
recreated with the organization.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.demo.history import HISTORY_HOURS, HistorySummary, play_history
from app.demo.seed import DEMO_ORG_SLUG, DemoSummary, seed_demo
from app.domains.exceptions.engine import run_evaluation
from app.domains.exceptions.models import EvaluationStatus, EvaluationTrigger
from app.domains.identity.models import Organization

logger = logging.getLogger("app.demo")

DEFAULT_SEED = 20261031
RESET_LOCK_KEY = 0x44454D4F  # "DEMO": session-level advisory lock held for a whole reset


class DemoBuildError(RuntimeError):
    pass


@dataclass
class DemoBuild:
    summary: DemoSummary
    history: HistorySummary
    first_evaluation: dict[str, int]
    final_evaluation: dict[str, int]


def demo_exists(db: Session) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(Organization)
            .where(Organization.slug == DEMO_ORG_SLUG, Organization.is_demo.is_(True))
        )
        or 0
    ) > 0


def _evaluate(db: Session, summary: DemoSummary, as_of: datetime) -> dict[str, int]:
    run = run_evaluation(db, summary.store_id, trigger=EvaluationTrigger.SCHEDULED, as_of=as_of)
    if run.status is not EvaluationStatus.SUCCEEDED:
        raise DemoBuildError(f"Demo evaluation {run.status.value}: {run.error}")
    db.commit()
    return dict(run.counts)


def build_demo(
    db: Session, *, now: datetime, seed: int = DEFAULT_SEED, staff_password: str | None = None
) -> DemoBuild:
    """Regenerate the demo organization so that it looks current at ``now``.

    The dataset is generated for ``now - HISTORY_HOURS`` and evaluated there; the team history
    then plays forward through the lifecycle service and two CSV imports, and a final scheduled
    evaluation runs at ``now``. Deterministic for a fixed ``seed`` and ``now`` (apart from ids).
    """
    start = now - timedelta(hours=HISTORY_HOURS)
    # Purge, dataset and first evaluation commit together: visitors never see an empty demo, and
    # the scheduled worker never finds the new store without a recent run (so it cannot evaluate
    # it in the middle of the scripted history).
    summary = seed_demo(db, now=start, seed=seed, staff_password=staff_password)
    first = _evaluate(db, summary, start)
    history = play_history(db, summary, start=start)
    final = _evaluate(db, summary, now)
    return DemoBuild(summary, history, first, final)


@contextmanager
def reset_lock(engine: Engine) -> Iterator[bool]:
    """Yield True while this process holds the demo reset lock, False if another reset runs."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        acquired = bool(conn.scalar(select(func.pg_try_advisory_lock(RESET_LOCK_KEY))))
        try:
            yield acquired
        finally:
            if acquired:
                conn.scalar(select(func.pg_advisory_unlock(RESET_LOCK_KEY)))
