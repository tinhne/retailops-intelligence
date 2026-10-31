"""Generate, or reset, the demo organization "Kestrel Commerce" (T-056, T-094).

    python -m app.demo                 # reset: regenerate the demo organization from the seed
    python -m app.demo --if-missing    # first start: seed only when no demo organization exists
    python -m app.demo --seed N        # a different (still deterministic) dataset

The reset is the scheduled demo reset job (docs/operations/DEMO_RESET.md). Only one reset runs at a
time (PostgreSQL advisory lock); a second one exits with status 3 and changes nothing.

Staff accounts (owner/manager/staff/sofia/analyst @kestrel.example) get the password from the
environment variable DEMO_STAFF_PASSWORD. If it is unset, a random password is generated and the
accounts are effectively login-disabled. DEMO_STAFF_PASSWORD is refused when APP_ENV=production:
public deployments only offer the passwordless read-only viewer (ADR-0011).
"""

import argparse
import logging
import os
import sys

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_engine, get_session_factory
from app.demo.build import DEFAULT_SEED, build_demo, demo_exists, reset_lock

logger = logging.getLogger("app.demo")

EXIT_LOCKED = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo",
        description="Generate or reset the fictional demo organization.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--if-missing",
        action="store_true",
        help="do nothing when a demo organization already exists (container start-up)",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    staff_password = os.environ.get("DEMO_STAFF_PASSWORD") or None
    if staff_password and settings.app_env == "production":
        logger.error("demo_staff_password_refused", extra={"app_env": settings.app_env})
        print("DEMO_STAFF_PASSWORD must not be set when APP_ENV=production.", file=sys.stderr)
        return 2

    with reset_lock(get_engine()) as acquired:
        if not acquired:
            logger.warning("demo_reset_skipped", extra={"reason": "another reset is running"})
            return EXIT_LOCKED
        with get_session_factory()() as db:
            if args.if_missing and demo_exists(db):
                logger.info("demo_seed_skipped", extra={"reason": "demo organization exists"})
                return 0
            result = build_demo(db, now=utcnow(), seed=args.seed, staff_password=staff_password)
    summary = result.summary
    logger.info(
        "demo_seeded",
        extra={
            "store_id": str(summary.store_id),
            "seed": args.seed,
            "products": summary.products,
            "orders": summary.orders,
            "order_lines": summary.order_lines,
            "movements": summary.movements,
            "imports": result.history.imports,
            "first_evaluation": result.first_evaluation,
            "import_evaluations": result.history.evaluations,
            "final_evaluation": result.final_evaluation,
            "scenarios": summary.scenarios,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
