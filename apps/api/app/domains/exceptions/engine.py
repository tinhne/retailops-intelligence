"""Exception evaluation entry point (EXCEPTION_CATALOG.md, STATE_MACHINES.md §3.3).

Contract used by imports, the manual trigger and the scheduler. Placeholder implementation until
T-053 lands: records a SKIPPED run so callers can integrate against the final signature.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.domains.exceptions.models import EvaluationRun, EvaluationStatus, EvaluationTrigger


def run_evaluation(
    db: Session,
    store_id: uuid.UUID,
    *,
    trigger: EvaluationTrigger,
    as_of: datetime,
    triggered_by: uuid.UUID | None = None,
    import_id: uuid.UUID | None = None,
    rule_ids: list[str] | None = None,
) -> EvaluationRun:
    """Evaluate rules for one store as of ``as_of`` and reconcile exceptions. Caller commits."""
    now = utcnow()
    run = EvaluationRun(
        store_id=store_id,
        trigger=trigger,
        status=EvaluationStatus.SKIPPED,
        as_of=as_of,
        rules=rule_ids or [],
        counts={},
        started_at=now,
        finished_at=now,
        duration_ms=0,
        triggered_by=triggered_by,
        import_id=import_id,
        error="Rule engine not implemented yet",
    )
    db.add(run)
    db.flush()
    return run
