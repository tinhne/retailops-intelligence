"""Fixtures for copilot tests: a small store with every record type the tools read, a scripted
fake LLM provider, and helpers to run tools and copilot turns."""

import dataclasses
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.ai.models import FallbackReason, ToolCallOrigin
from app.domains.ai.providers.base import (
    AssistantMessage,
    FinalStep,
    ProviderFailure,
    ProviderRequest,
    ProviderStep,
    TextStep,
    ToolCallsStep,
    ToolRequest,
    Usage,
)
from app.domains.ai.runtime import CopilotRuntime
from app.domains.ai.tools.registry import TurnTools
from app.domains.catalog.models import Product
from app.domains.exceptions.models import (
    ExceptionType,
    OperationalException,
    Severity,
)
from app.domains.identity import service as identity
from app.domains.identity.models import User
from app.domains.identity.permissions import Permission, Role
from app.domains.identity.service import StoreContext
from app.domains.imports.models import ImportRowIssue, ImportStatus, ImportType, IssueSeverity
from app.domains.inventory.models import MovementType
from app.domains.orders.models import Order, OrderStatus
from tests.factories import Tenant, create_tenant, create_user, login
from tests.factories_commerce import (
    Line,
    count_stock,
    create_evaluation_run,
    create_exception,
    create_import,
    create_order,
    create_product,
    create_supplier,
    move_stock,
)

NOW = datetime(2026, 11, 3, 17, 0, tzinfo=UTC)


@dataclass
class AIStore:
    tenant: Tenant
    manager: User
    mug: Product
    pan: Product
    overdue_order: Order
    pending_order: Order
    overdue_exception: OperationalException
    stock_exception: OperationalException
    import_id: uuid.UUID

    @property
    def store_id(self) -> uuid.UUID:
        return self.tenant.store.id


def build_store(db: Session, slug: str, *, prefix: str = "KH") -> AIStore:
    """One store: two products (one below reorder point), an overdue paid order, a pending order,
    two exceptions, an import with row issues and an evaluation run. ``prefix`` lets two stores
    share SKUs and order numbers (tenancy tests)."""
    tenant = create_tenant(db, slug)
    manager = create_user(db, tenant, Role.MANAGER)
    supplier = create_supplier(db, tenant, "Harbor Ceramics", lead_time_days=14)
    mug = create_product(
        db,
        tenant,
        f"{prefix}-MUG-01",
        name="Stoneware Mug",
        reorder_point=5,
        supplier=supplier,
        unit_price="12.00",
    )
    pan = create_product(db, tenant, f"{prefix}-PAN-10", name="Cast Iron Pan", unit_price="40.00")
    count_stock(db, tenant, mug, 4, NOW - timedelta(days=10))
    count_stock(db, tenant, pan, 20, NOW - timedelta(days=10))
    move_stock(db, tenant, pan, MovementType.DAMAGE, 2, NOW - timedelta(days=2), note="Dropped")
    overdue = create_order(
        db,
        tenant,
        f"{prefix}-1001",
        status=OrderStatus.PAID,
        lines=[Line(pan, 1, "40.00")],
        placed_at=NOW - timedelta(days=5),
        ship_by=NOW - timedelta(hours=30),
    )
    pending = create_order(
        db,
        tenant,
        f"{prefix}-1002",
        status=OrderStatus.PAYMENT_PENDING,
        lines=[Line(mug, 2, "12.00")],
        placed_at=NOW - timedelta(hours=3),
    )
    overdue_exc = create_exception(
        db,
        tenant,
        ExceptionType.ORDER_FULFILLMENT_OVERDUE,
        entity=overdue,
        first_detected_at=NOW - timedelta(hours=6),
        severity=Severity.HIGH,
        priority_score=72,
        exposure_amount=Decimal("40.00"),
        title=f"Order {prefix}-1001 is past its ship-by deadline",
    )
    stock_exc = create_exception(
        db,
        tenant,
        ExceptionType.INVENTORY_BELOW_REORDER_POINT,
        entity=mug,
        first_detected_at=NOW - timedelta(days=2),
        severity=Severity.MEDIUM,
        priority_score=30,
        title=f"Below reorder point: {prefix}-MUG-01",
    )
    record = create_import(
        db,
        tenant,
        ImportType.ORDERS,
        status=ImportStatus.COMPLETED_WITH_ERRORS,
        applied_at=NOW - timedelta(hours=2),
    )
    db.add_all(
        [
            ImportRowIssue(
                import_id=record.id,
                row_number=7,
                column="placed_at",
                code="INVALID_DATETIME",
                severity=IssueSeverity.ERROR,
                message="Not an ISO-8601 timestamp",
                raw_value="31/10/2026 9am",
            ),
            ImportRowIssue(
                import_id=record.id,
                row_number=9,
                column="payment_status",
                code="ORDER_INVALID_STATUS_COMBINATION",
                severity=IssueSeverity.ERROR,
                message="status SHIPPED requires payment_status PAID",
                raw_value="PENDING",
            ),
        ]
    )
    db.commit()
    create_evaluation_run(db, tenant, started_at=NOW - timedelta(hours=1))
    return AIStore(tenant, manager, mug, pan, overdue, pending, overdue_exc, stock_exc, record.id)


def store_context(db: Session, user: User, store_id: uuid.UUID) -> StoreContext:
    return identity.store_context(db, user, store_id)


def without(ctx: StoreContext, *permissions: Permission) -> StoreContext:
    return dataclasses.replace(ctx, permissions=ctx.permissions - set(permissions))


def turn_tools(engine: Engine, ctx: StoreContext, settings: Settings, **limits: Any) -> TurnTools:
    return TurnTools(
        engine, ctx, as_of=NOW, settings=settings.model_copy(update=limits) if limits else settings
    )


def run(tools: TurnTools, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return tools.execute(name, args or {}, ToolCallOrigin.MODEL)


def refs(envelope: dict[str, Any]) -> set[str]:
    """Every ``type:id`` reference anywhere in a result envelope."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("ref") if isinstance(node.get("ref"), dict) else None
            if ref and "type" in ref and "id" in ref:
                found.add(f"{ref['type']}:{ref['id']}")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(envelope)
    return found


# --- a scripted live provider --------------------------------------------------------------------

Script = Callable[[ProviderRequest, int], ProviderStep]


@dataclass
class FakeProvider:
    """Replays scripted steps. ``requests`` records what the engine sent."""

    script: Script
    name: str = "gemini"
    model: str = "fake-flash"
    requests: list[ProviderRequest] = field(default_factory=list)

    def next_step(self, request: ProviderRequest) -> ProviderStep:
        self.requests.append(request)
        return self.script(request, len(self.requests) - 1)


def final(arguments: Any) -> FinalStep:
    call = ToolRequest(id="out", name="submit_answer", arguments=arguments)
    return FinalStep(arguments, AssistantMessage(tool_calls=(call,)), Usage(100, 20))


def tool_calls(*calls: tuple[str, dict[str, Any]]) -> ToolCallsStep:
    requests = tuple(ToolRequest(id=f"c{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls))
    return ToolCallsStep(requests, AssistantMessage(tool_calls=requests), Usage(100, 10))


def text(content: str) -> TextStep:
    return TextStep(content, AssistantMessage(text=content), Usage(100, 10))


def failing(reason: FallbackReason, retry_after: float | None = None) -> Script:
    def script(request: ProviderRequest, index: int) -> ProviderStep:
        raise ProviderFailure(reason, "scripted failure", retry_after=retry_after)

    return script


def live_settings(settings: Settings, **overrides: Any) -> Settings:
    return settings.model_copy(
        update={
            "llm_provider": "gemini",
            "gemini_api_key": SecretStr("test-key-not-real"),
            **overrides,
        }
    )


def install_runtime(
    app: FastAPI, settings: Settings, provider: FakeProvider | None = None, **kwargs: Any
) -> CopilotRuntime:
    """A runtime with a fixed clock, no outbound network, and optionally a scripted provider."""

    def blocked(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not happen
        raise AssertionError(f"unexpected outbound request to {request.url.host}")

    runtime = CopilotRuntime(
        settings,
        provider_factory=(lambda _s, _c: provider) if provider is not None else _no_provider,
        clock=lambda: NOW,
        http_client=httpx.Client(transport=httpx.MockTransport(blocked)),
        **kwargs,
    )
    app.state.copilot = runtime
    return runtime


def _no_provider(settings: Settings, client: httpx.Client) -> None:
    return None


def sign_in(client: TestClient, user: User) -> dict[str, str]:
    return {"X-CSRF-Token": login(client, user.email)}
