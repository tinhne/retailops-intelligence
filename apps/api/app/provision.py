"""Onboard a customer: organization, first store and owner account.

    python -m app.provision --org-name "Lotus Home" --store-name "Lotus Home Online" \
        --currency VND --timezone Asia/Ho_Chi_Minh \
        --owner-email owner@lotushome.vn --owner-name "Nguyen Van An" [--exposure-cap 100000000]

In the container stack: ``docker compose run --rm --no-deps api python -m app.provision ...``.
The owner's temporary password is printed once; hand it over securely. Nothing else is printed.
"""

import argparse
import sys
from decimal import Decimal, InvalidOperation

from app.core.errors import AppError
from app.db.session import get_session_factory
from app.domains.identity.provisioning import ProvisionRequest, provision


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not a number: {value}") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a customer organization, store and owner.")
    parser.add_argument("--org-name", required=True, help="Organization (company) name")
    parser.add_argument("--slug", help="URL-safe organization id (default: from the name)")
    parser.add_argument("--store-name", required=True, help="Store name shown in the app")
    parser.add_argument("--store-code", help="Short store code (default: from the store name)")
    parser.add_argument("--currency", required=True, help="ISO 4217 code of the store, e.g. VND")
    parser.add_argument("--timezone", required=True, help="IANA time zone, e.g. Asia/Ho_Chi_Minh")
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--owner-name", required=True)
    parser.add_argument(
        "--exposure-cap",
        type=_decimal,
        help="Value at risk that earns full priority points, in store currency (default 5000)",
    )
    args = parser.parse_args(argv)

    request = ProvisionRequest(
        organization_name=args.org_name,
        slug=args.slug,
        store_name=args.store_name,
        store_code=args.store_code,
        currency=args.currency.upper(),
        timezone=args.timezone,
        owner_email=args.owner_email,
        owner_name=args.owner_name,
        exposure_cap=args.exposure_cap,
    )
    with get_session_factory()() as db:
        try:
            result = provision(db, request)
        except AppError as exc:
            print(f"error: {exc.message} ({exc.code})", file=sys.stderr)
            return 2

    print(f"organization_id: {result.organization_id}")
    print(f"store_id:        {result.store_id}")
    print(f"owner:           {result.owner_email}")
    print(f"temporary password (shown once): {result.temporary_password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
