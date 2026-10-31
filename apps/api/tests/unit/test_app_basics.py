"""App-level behavior that needs no database: liveness, error envelope, request IDs, settings."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from tests.conftest import make_settings


@pytest.fixture
def bare_client() -> TestClient:
    return TestClient(create_app(make_settings()))


def test_liveness(bare_client: TestClient) -> None:
    response = bare_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_error_envelope_with_request_id(bare_client: TestClient) -> None:
    response = bare_client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "req-12345678"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"] == "req-12345678"
    assert response.headers["x-request-id"] == "req-12345678"


def test_invalid_request_id_is_replaced(bare_client: TestClient) -> None:
    response = bare_client.get("/api/v1/health/live", headers={"X-Request-ID": "<script>"})
    assert response.headers["x-request-id"] != "<script>"
    assert len(response.headers["x-request-id"]) == 32


def test_validation_errors_use_envelope(bare_client: TestClient) -> None:
    response = bare_client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_FAILED"
    assert any(d["loc"][-1] == "password" for d in body["details"])


def test_production_requires_secret_and_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", cookie_secure=True)
    with pytest.raises(ValidationError):
        Settings(app_env="production", session_secret="x" * 40, cookie_secure=False)  # type: ignore[arg-type]
    Settings(app_env="production", session_secret="x" * 40, cookie_secure=True)  # type: ignore[arg-type]
