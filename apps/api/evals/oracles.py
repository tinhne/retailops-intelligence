"""Selectors and oracles (EVALUATION_STRATEGY.md §2.1).

Cases never contain expected numbers or ids: the demo data is generated relative to the run's
``as_of``. **Selectors** pick entities from the database at evaluation time; **oracles** compute
expected values at the same ``as_of``. Oracles call the domain services directly, never the tool
registry, so a defect in a tool wrapper (wrong filter, wrong field, broken scoping) shows up as a
mismatch. A defect inside a domain service would affect both and is covered by pytest instead.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.domains.ai.providers.deterministic.plans import PlanContext, start_of_yesterday
from app.domains.analytics import service as analytics
from app.domains.catalog.models import Product
from app.domains.exceptions import service as exceptions
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    EvaluationRun,
    ExceptionNote,
    ExceptionStatus,
    ExceptionType,
    OperationalException,
    PriorityBand,
    Severity,
)
from app.domains.identity.models import Store
from app.domains.identity.store_service import get_settings
from app.domains.imports.models import DataImport
from app.domains.inventory import queries as inventory
from app.domains.orders import queries as orders
from app.domains.orders.models import Order
from app.domains.orders.state import COMMITTED_STATUSES
from evals.environment import Stores

Vars = dict[str, SimpleNamespace]


@dataclass
class OracleContext:
    db: Session
    stores: Stores
    store: Store
    as_of: datetime
    vars: Vars = field(default_factory=dict)


# --- selectors -----------------------------------------------------------------------------------


def _exception_ns(exc: OperationalException) -> SimpleNamespace:
    return SimpleNamespace(
        id=exc.id,
        ref=f"exception:{exc.id}",
        reference=exc.reference,
        title=exc.title,
        exception_type=exc.exception_type.value,
        store_id=exc.store_id,
    )


def select_entity(
    db: Session, stores: Stores, default: Store, spec: dict[str, Any], as_of: datetime
) -> SimpleNamespace | None:
    """Resolve one ``select`` entry. Returns None when nothing matches (case ERROR)."""
    store = stores.by_name(spec["store"]) if "store" in spec else default
    kind = spec["kind"]
    if kind == "exception":
        stmt = select(OperationalException).where(OperationalException.store_id == store.id)
        if "exception_type" in spec:
            stmt = stmt.where(
                OperationalException.exception_type == ExceptionType(spec["exception_type"])
            )
        if "severity" in spec:
            stmt = stmt.where(OperationalException.severity == Severity(spec["severity"]))
        status = spec.get("status", "active")
        if status == "active":
            stmt = stmt.where(OperationalException.status.in_(ACTIVE_STATUSES))
        elif status != "any":
            stmt = stmt.where(OperationalException.status == ExceptionStatus(status))
        if spec.get("has_note"):
            stmt = stmt.where(
                select(ExceptionNote.id)
                .where(ExceptionNote.exception_id == OperationalException.id)
                .exists()
            )
        stmt = stmt.order_by(
            OperationalException.priority_score.desc(),
            OperationalException.due_at,
            OperationalException.reference,
        )
        exc = db.scalars(stmt.limit(1)).first()
        return _exception_ns(exc) if exc else None
    if kind == "order":
        order_stmt = select(Order).where(Order.store_id == store.id)
        if "shared_number_with" in spec:
            other = stores.by_name(spec["shared_number_with"])
            order_stmt = order_stmt.where(
                Order.order_number.in_(select(Order.order_number).where(Order.store_id == other.id))
            )
        if spec.get("overdue"):
            order_stmt = order_stmt.where(orders.overdue_condition(as_of))
        order = db.scalars(order_stmt.order_by(Order.ship_by, Order.order_number).limit(1)).first()
        if order is None:
            return None
        return SimpleNamespace(
            id=order.id,
            ref=f"order:{order.id}",
            order_number=order.order_number,
            status=order.status.value,
        )
    if kind == "product":
        product_stmt = select(Product).where(Product.store_id == store.id)
        if "exception_type" in spec:
            product_stmt = product_stmt.where(
                Product.id.in_(
                    select(OperationalException.primary_entity_id).where(
                        OperationalException.store_id == store.id,
                        OperationalException.exception_type
                        == ExceptionType(spec["exception_type"]),
                        OperationalException.status.in_(ACTIVE_STATUSES),
                    )
                )
            )
        product = db.scalars(product_stmt.order_by(Product.sku).limit(1)).first()
        if product is None:
            return None
        return SimpleNamespace(
            id=product.id, ref=f"product:{product.id}", sku=product.sku, name=product.name
        )
    raise ValueError(f"unknown selector kind {kind}")


# --- oracles -------------------------------------------------------------------------------------


def _exceptions(ctx: OracleContext, n: int, **filters: Any) -> list[str]:
    items, _ = exceptions.list_exceptions(
        ctx.db,
        ctx.store.id,
        current_user_id=uuid.uuid4(),
        filters=exceptions.ExceptionFilters(**filters),
        sort="-priority_score",
        offset=0,
        limit=n,
        now=ctx.as_of,
    )
    return [f"exception:{item.id}" for item in items]


def top_active_exceptions_by_priority(ctx: OracleContext, n: int) -> list[str]:
    return _exceptions(ctx, n)


def active_exceptions_of_type(ctx: OracleContext, exception_type: str, n: int) -> list[str]:
    return _exceptions(ctx, n, exception_types=[ExceptionType(exception_type)])


def active_exceptions_of_severity(ctx: OracleContext, severity: str, n: int) -> list[str]:
    return _exceptions(ctx, n, severities=[Severity(severity)])


def p1_unassigned_exceptions(ctx: OracleContext, n: int) -> list[str]:
    return _exceptions(ctx, n, priority_bands=[PriorityBand.P1], assignee="unassigned")


def top_priority_score(ctx: OracleContext) -> int:
    items, _ = exceptions.list_exceptions(
        ctx.db,
        ctx.store.id,
        current_user_id=uuid.uuid4(),
        filters=exceptions.ExceptionFilters(),
        limit=1,
        now=ctx.as_of,
    )
    return items[0].priority_score


def _overdue_page(ctx: OracleContext, n: int) -> Any:
    return orders.list_orders(
        ctx.db,
        ctx.store.id,
        filters=orders.OrderFilters(statuses=list(COMMITTED_STATUSES), overdue=True),
        sort="ship_by",
        paging=PageParams(page=1, page_size=n),
        as_of=ctx.as_of,
    )


def overdue_order_count(ctx: OracleContext) -> int:
    return int(_overdue_page(ctx, 1).total)


def oldest_overdue_orders(ctx: OracleContext, n: int) -> list[str]:
    return [f"order:{item.id}" for item in _overdue_page(ctx, n).items]


def _dashboard(ctx: OracleContext) -> Any:
    settings = get_settings(ctx.db, ctx.store.id)
    return analytics.get_dashboard_summary(
        ctx.db,
        ctx.store.id,
        timezone=ctx.store.timezone,
        currency=ctx.store.currency,
        approaching_factor=settings.approaching_reorder_factor,
        as_of=ctx.as_of,
    )


def active_exception_count(ctx: OracleContext) -> int:
    return int(_dashboard(ctx).active_exceptions.total)


def exceptions_detected_since_yesterday(ctx: OracleContext) -> int:
    since = start_of_yesterday(PlanContext(as_of=ctx.as_of, timezone=ctx.store.timezone))
    _, total = exceptions.list_exceptions(
        ctx.db,
        ctx.store.id,
        current_user_id=uuid.uuid4(),
        filters=exceptions.ExceptionFilters(statuses=list(ExceptionStatus), detected_from=since),
        limit=1,
        now=ctx.as_of,
    )
    return total


def trend_total(ctx: OracleContext, metric: str, days: int) -> Any:
    trends = analytics.get_trends(
        ctx.db,
        ctx.store.id,
        timezone=ctx.store.timezone,
        currency=ctx.store.currency,
        days=days,
        as_of=ctx.as_of,
    )
    return getattr(trends.totals, metric)


def selected(ctx: OracleContext, var: str) -> list[str]:
    return [str(ctx.vars[var].ref)]


def exception_field(ctx: OracleContext, var: str, field: str) -> Any:
    exc = ctx.db.get(OperationalException, ctx.vars[var].id)
    assert exc is not None
    value = getattr(exc, field)
    return value.value if hasattr(value, "value") else value


def exception_evidence_value(ctx: OracleContext, var: str, key: str) -> Any:
    exc = ctx.db.get(OperationalException, ctx.vars[var].id)
    assert exc is not None
    for item in (exc.evidence or {}).get("facts") or []:
        if item.get("key") == key:
            return item.get("value")
    return None


def product_available(ctx: OracleContext, var: str) -> int:
    return inventory.get_stock(ctx.db, ctx.store.id, ctx.vars[var].id).available


def order_status(ctx: OracleContext, var: str) -> str:
    return str(ctx.vars[var].status)


def order_by_number(ctx: OracleContext, var: str) -> list[str]:
    number = ctx.vars[var].order_number
    order_id = ctx.db.scalar(
        select(Order.id).where(Order.store_id == ctx.store.id, Order.order_number == number)
    )
    return [f"order:{order_id}"]


def latest_import(ctx: OracleContext) -> list[str]:
    import_id = ctx.db.scalar(
        select(DataImport.id)
        .where(DataImport.store_id == ctx.store.id)
        .order_by(DataImport.created_at.desc())
        .limit(1)
    )
    return [f"import:{import_id}"]


def all_refs_of_store(ctx: OracleContext, store: str) -> list[str]:
    target = ctx.stores.by_name(store)
    keys: list[str] = []
    for kind, model in (
        ("product", Product),
        ("order", Order),
        ("exception", OperationalException),
        ("import", DataImport),
        ("evaluation_run", EvaluationRun),
    ):
        ids = ctx.db.scalars(select(model.id).where(model.store_id == target.id)).all()
        keys += [f"{kind}:{i}" for i in ids]
    return keys


def literal(ctx: OracleContext, value: Any) -> Any:
    return value


ORACLES: dict[str, Callable[..., Any]] = {
    fn.__name__: fn
    for fn in (
        top_active_exceptions_by_priority,
        active_exceptions_of_type,
        active_exceptions_of_severity,
        p1_unassigned_exceptions,
        top_priority_score,
        overdue_order_count,
        oldest_overdue_orders,
        active_exception_count,
        exceptions_detected_since_yesterday,
        trend_total,
        selected,
        exception_field,
        exception_evidence_value,
        product_available,
        order_status,
        order_by_number,
        latest_import,
        all_refs_of_store,
        literal,
    )
}


def oracle(name: str, ctx: OracleContext, args: dict[str, Any] | None) -> Any:
    return ORACLES[name](ctx, **(args or {}))
