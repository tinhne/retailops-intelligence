"""App-level behavior that needs no database: liveness, error envelope, request IDs, settings."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from app.domains.imports.parsing import MAX_FILE_BYTES
from app.main import MAX_REQUEST_BODY_BYTES, create_app
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
    csrf = bare_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = bare_client.post(
        "/api/v1/auth/login", json={"email": "not-an-email"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_FAILED"
    assert any(d["loc"][-1] == "password" for d in body["details"])


def test_api_responses_carry_security_headers(bare_client: TestClient) -> None:
    for response in (
        bare_client.get("/api/v1/health/live"),
        bare_client.get("/api/v1/does-not-exist"),
    ):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"


@pytest.fixture
def small_body_client() -> TestClient:
    """A tiny app behind the body limit (10 bytes) and the standard error handlers."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"received": len(await request.body())}

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=10)
    app.add_middleware(RequestContextMiddleware)
    return TestClient(app)


def test_body_limit_refuses_a_declared_oversized_body_before_reading_it(
    small_body_client: TestClient,
) -> None:
    ok = small_body_client.post("/echo", content=b"x" * 10)
    too_big = small_body_client.post("/echo", content=b"x" * 11)

    assert ok.json() == {"received": 10}
    assert too_big.status_code == 413
    assert too_big.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert too_big.json()["error"]["request_id"] == too_big.headers["x-request-id"]


def test_body_limit_stops_a_streamed_body_without_content_length(
    small_body_client: TestClient,
) -> None:
    response = small_body_client.post("/echo", content=iter([b"x" * 6, b"x" * 6]))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_upload_limit_leaves_room_for_a_rejected_file_record() -> None:
    """BR-602: a file just over 5 MB still reaches the import service (recorded as REJECTED)."""
    assert MAX_REQUEST_BODY_BYTES > MAX_FILE_BYTES + 64 * 1024


def test_production_requires_secret_and_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", cookie_secure=True)
    with pytest.raises(ValidationError):
        Settings(app_env="production", session_secret="x" * 40, cookie_secure=False)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):  # the .env.example placeholder
        Settings(app_env="production", session_secret="change-me", cookie_secure=True)  # type: ignore[arg-type]
    Settings(app_env="production", session_secret="x" * 40, cookie_secure=True)  # type: ignore[arg-type]
