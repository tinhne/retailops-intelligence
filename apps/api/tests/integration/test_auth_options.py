"""Public sign-in options: the demo is offered only where it exists (ADR-0011)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domains.identity.permissions import Role
from tests.conftest import make_settings
from tests.factories import create_tenant, create_user

pytestmark = pytest.mark.integration


def test_demo_is_available_when_enabled_and_the_viewer_exists(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db, "kestrel", is_demo=True)
    create_user(db, tenant, Role.VIEWER, email="demo@kestrel.example")

    response = client.get("/api/v1/auth/options")

    assert response.status_code == 200
    assert response.json() == {"demo_available": True}


def test_customer_install_without_demo_seed_offers_no_demo(client: TestClient, db: Session) -> None:
    create_tenant(db, "lotus")  # a real customer, no demo viewer account
    assert client.get("/api/v1/auth/options").json() == {"demo_available": False}


def test_demo_mode_off_hides_the_demo_even_if_seeded(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db, "kestrel", is_demo=True)
    create_user(db, tenant, Role.VIEWER, email="demo@kestrel.example")
    app.dependency_overrides[get_settings] = lambda: make_settings(demo_mode_enabled=False)

    assert client.get("/api/v1/auth/options").json() == {"demo_available": False}
