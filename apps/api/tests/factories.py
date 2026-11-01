"""Small factory helpers for integration tests."""

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.identity.models import Membership, Organization, Store, StoreSettings, User
from app.domains.identity.permissions import Role
from app.domains.identity.security import hash_password
from app.domains.identity.service import normalize_email

DEFAULT_PASSWORD = "correct-horse-battery-staple"


@dataclass
class Tenant:
    organization: Organization
    store: Store


def create_tenant(db: Session, slug: str = "acme", *, is_demo: bool = False) -> Tenant:
    org = Organization(name=f"{slug.title()} Commerce", slug=slug, is_demo=is_demo)
    db.add(org)
    db.flush()
    store = Store(
        organization_id=org.id,
        name=f"{slug.title()} Store",
        code=slug[:8].upper(),
        currency="USD",
        timezone="America/New_York",
    )
    db.add(store)
    db.flush()
    db.add(StoreSettings(store_id=store.id))
    db.commit()
    return Tenant(organization=org, store=store)


def create_user(
    db: Session,
    tenant: Tenant,
    role: Role,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
) -> User:
    user = User(
        email=normalize_email(email or f"{role.value.lower()}@{tenant.organization.slug}.example"),
        full_name=f"{role.value.title()} User",
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=tenant.organization.id, role=role))
    db.commit()
    return user


def pre_session_csrf(client: TestClient) -> dict[str, str]:
    """Fetch the sign-in CSRF token (``GET /auth/csrf``, ADR-0004) as request headers."""
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> str:
    """Sign in and return the CSRF token for subsequent mutating requests."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=pre_session_csrf(client),
    )
    assert response.status_code == 200, response.text
    token: str = response.json()["csrf_token"]
    return token
