"""Customer onboarding: organization, first store and its owner (ROLE_AND_PERMISSION_WORKFLOW §8).

v1 has no self-service sign-up and no email delivery. An operator runs ``python -m app.provision``
once per customer; the owner then signs in with the temporary password shown once, adds the team
under Users & roles, and imports the store's CSV exports. Everything else (settings, members,
data) is managed in the product.
"""

import re
import secrets
import uuid
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolationError, ConflictError
from app.domains.audit import service as audit
from app.domains.identity import security
from app.domains.identity.member_service import TEMPORARY_PASSWORD_BYTES
from app.domains.identity.models import Membership, Organization, Store, StoreSettings, User
from app.domains.identity.permissions import Role
from app.domains.identity.service import normalize_email

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class ProvisionRequest:
    organization_name: str
    store_name: str
    currency: str
    timezone: str
    owner_email: str
    owner_name: str
    slug: str | None = None
    store_code: str | None = None
    exposure_cap: Decimal | None = None


@dataclass(frozen=True)
class Provisioned:
    organization_id: uuid.UUID
    store_id: uuid.UUID
    owner_id: uuid.UUID
    owner_email: str
    temporary_password: str  # shown once, never stored in clear


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or "organization"


def _invalid(message: str, field: str) -> BusinessRuleViolationError:
    return BusinessRuleViolationError(
        message, code="INVALID_PROVISIONING", details=[{"field": field}]
    )


def _validate(request: ProvisionRequest) -> tuple[str, str, str]:
    """Return (slug, store code, normalized owner email) or raise with the offending field."""
    if not request.organization_name.strip() or len(request.organization_name) > 200:
        raise _invalid(
            "Organization name is required (at most 200 characters).", "organization_name"
        )
    if not request.store_name.strip() or len(request.store_name) > 200:
        raise _invalid("Store name is required (at most 200 characters).", "store_name")
    if not request.owner_name.strip() or len(request.owner_name) > 200:
        raise _invalid("Owner name is required (at most 200 characters).", "owner_name")
    slug = request.slug or slugify(request.organization_name)
    if not _SLUG.match(slug) or len(slug) > 80:
        raise _invalid("Slug must be lowercase letters, digits and hyphens.", "slug")
    if not _CURRENCY.match(request.currency):
        raise _invalid(
            "Currency must be a three-letter ISO 4217 code, e.g. USD or VND.", "currency"
        )
    try:
        ZoneInfo(request.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise _invalid(
            "Time zone must be an IANA name, e.g. Asia/Ho_Chi_Minh or America/New_York.", "timezone"
        ) from None
    if request.timezone not in available_timezones():
        raise _invalid("Time zone must be an IANA name.", "timezone")
    email = normalize_email(request.owner_email)
    if not _EMAIL.match(email) or len(email) > 254:
        raise _invalid("Owner email is not a valid address.", "owner_email")
    code = (request.store_code or slugify(request.store_name).replace("-", "")[:8]).upper()
    if not code or len(code) > 32:
        raise _invalid("Store code must be 1 to 32 characters.", "store_code")
    if request.exposure_cap is not None and request.exposure_cap <= 0:
        raise _invalid("Exposure cap must be greater than zero.", "exposure_cap")
    return slug, code, email


def provision(db: Session, request: ProvisionRequest) -> Provisioned:
    """Create the organization, its store with default settings, and the owner. Commits."""
    slug, code, email = _validate(request)
    if db.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        raise ConflictError(
            f"An organization with the slug '{slug}' already exists.", code="ORG_SLUG_IN_USE"
        )
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("An account with this email already exists.", code="EMAIL_IN_USE")

    organization = Organization(name=request.organization_name.strip(), slug=slug, is_demo=False)
    db.add(organization)
    db.flush()
    store = Store(
        organization_id=organization.id,
        name=request.store_name.strip(),
        code=code,
        currency=request.currency,
        timezone=request.timezone,
    )
    db.add(store)
    db.flush()
    settings = StoreSettings(store_id=store.id)
    if request.exposure_cap is not None:
        settings.exposure_cap = request.exposure_cap
    db.add(settings)

    temporary_password = secrets.token_urlsafe(TEMPORARY_PASSWORD_BYTES)
    owner = User(
        email=email,
        full_name=request.owner_name.strip(),
        password_hash=security.hash_password(temporary_password),
    )
    db.add(owner)
    db.flush()
    db.add(Membership(user_id=owner.id, organization_id=organization.id, role=Role.OWNER))
    audit.record(
        db,
        action="organization.provision",
        organization_id=organization.id,
        actor_user_id=None,
        store_id=store.id,
        target_type="organization",
        target_id=organization.id,
        details={"store_code": code, "currency": request.currency, "timezone": request.timezone},
    )
    db.commit()
    return Provisioned(
        organization_id=organization.id,
        store_id=store.id,
        owner_id=owner.id,
        owner_email=email,
        temporary_password=temporary_password,
    )
