"""Generate (or regenerate) the demo dataset.

    python -m app.demo [--seed N] [--staff-password-env VAR]

Staff accounts (owner/manager/staff/analyst @kestrel.example) get the password from the
environment variable DEMO_STAFF_PASSWORD; if it is unset a random password is generated and the
accounts are effectively login-disabled. The public demo uses the passwordless read-only viewer.
"""

import argparse
import logging
import os

from app.core.clock import utcnow
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.demo.seed import seed_demo
from app.domains.exceptions.engine import run_evaluation
from app.domains.exceptions.models import EvaluationTrigger

logger = logging.getLogger("app.demo")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261031)
    args = parser.parse_args()
    configure_logging("INFO")

    now = utcnow()
    with get_session_factory()() as db:
        summary = seed_demo(
            db, now=now, seed=args.seed, staff_password=os.environ.get("DEMO_STAFF_PASSWORD")
        )
        db.commit()
        run = run_evaluation(db, summary.store_id, trigger=EvaluationTrigger.SCHEDULED, as_of=now)
        db.commit()
        logger.info(
            "demo_seeded",
            extra={
                "store_id": str(summary.store_id),
                "products": summary.products,
                "orders": summary.orders,
                "order_lines": summary.order_lines,
                "movements": summary.movements,
                "evaluation_status": run.status.value,
                "evaluation_counts": run.counts,
                "scenarios": summary.scenarios,
            },
        )


if __name__ == "__main__":
    main()
