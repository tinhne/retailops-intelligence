"""Scheduled evaluation worker (T-055, ADR-0009).

Time-based rules (overdue, stalled, refund pending, priority age) only advance when an evaluation
runs, so each store is evaluated every ``evaluation_interval_minutes``. A store is due
when its most recent run of any trigger started at least one interval ago: an import-triggered or
manual run resets the clock, so the worker never duplicates fresh work.

Every store is evaluated in its own unit of work. The engine's per-store advisory lock prevents
overlap with manual or import-triggered runs (a collision is recorded as SKIPPED, not an error).
This is the only background process in the system.

Usage:
    python -m app.workers.scheduler            # run forever
    python -m app.workers.scheduler --once     # one pass, e.g. from an external cron
    python -m app.workers.scheduler --heartbeat /tmp/worker-heartbeat   # container health check
"""

import argparse
import logging
import signal
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from types import FrameType

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.domains.exceptions.engine import run_evaluation
from app.domains.exceptions.models import EvaluationRun, EvaluationTrigger
from app.domains.identity.models import StoreSettings

logger = logging.getLogger("app.worker")
POLL_SECONDS = 60


def due_store_ids(db: Session, now: datetime) -> list[uuid.UUID]:
    """Stores whose latest evaluation run started at least one interval before ``now``."""
    latest = (
        select(EvaluationRun.store_id, func.max(EvaluationRun.started_at).label("last_started"))
        .group_by(EvaluationRun.store_id)
        .subquery()
    )
    rows = db.execute(
        select(
            StoreSettings.store_id, StoreSettings.evaluation_interval_minutes, latest.c.last_started
        )
        .outerjoin(latest, latest.c.store_id == StoreSettings.store_id)
        .order_by(latest.c.last_started.asc().nulls_first())
    ).all()
    return [
        store_id
        for store_id, interval, last_started in rows
        if last_started is None or now - last_started >= timedelta(minutes=interval)
    ]


def run_once(
    session_factory: sessionmaker[Session], *, clock: Callable[[], datetime] = utcnow
) -> list[EvaluationRun]:
    """Evaluate every due store once. A failing store never stops the others."""
    with session_factory() as db:
        store_ids = due_store_ids(db, clock())
    runs: list[EvaluationRun] = []
    for store_id in store_ids:
        with session_factory() as db:
            try:
                run = run_evaluation(
                    db, store_id, trigger=EvaluationTrigger.SCHEDULED, as_of=clock()
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("scheduled_evaluation_crashed", extra={"store_id": str(store_id)})
                continue
            runs.append(run)
            logger.info(
                "scheduled_evaluation",
                extra={
                    "store_id": str(store_id),
                    "status": run.status.value,
                    "counts": run.counts,
                    "duration_ms": run.duration_ms,
                },
            )
    return runs


def touch_heartbeat(path: Path | None) -> None:
    """Record that a pass finished; the container health check reads the file's age."""
    if path is None:
        return
    try:
        path.touch()
    except OSError:
        logger.warning("worker_heartbeat_failed", extra={"path": str(path)}, exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="RetailOps scheduled evaluation worker")
    parser.add_argument("--once", action="store_true", help="run a single pass and exit")
    parser.add_argument(
        "--heartbeat",
        type=Path,
        default=None,
        help="file touched after every pass (for container health checks)",
    )
    args = parser.parse_args()
    configure_logging(get_settings().log_level)
    factory = get_session_factory()

    if args.once:
        run_once(factory)
        return

    stop = threading.Event()

    def _request_stop(signum: int, _frame: FrameType | None) -> None:
        logger.info("worker_stopping", extra={"signal": signum})
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    logger.info("worker_started", extra={"poll_seconds": POLL_SECONDS})
    while not stop.is_set():
        try:
            run_once(factory)
        except Exception:
            logger.exception("worker_pass_failed")
        else:
            touch_heartbeat(args.heartbeat)
        stop.wait(POLL_SECONDS)
    logger.info("worker_stopped")


if __name__ == "__main__":
    main()
