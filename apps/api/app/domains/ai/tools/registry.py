"""The allowlisted tool registry and the per-turn executor (TOOL_CATALOG.md §1, AI_ARCHITECTURE §6).

``TOOLS`` is the closed allowlist: exactly the 11 read-only tools of the catalog. There is no raw
SQL, write, cross-store, user-lookup or external tool. ``TurnTools`` executes calls for one turn,
whichever provider asked for them, so every guardrail lives in one place:

1. unknown names → ``UNKNOWN_TOOL``; more than the per-turn cap → ``REJECTED_LIMIT``;
2. arguments validated by the tool's Pydantic model (unknown fields rejected);
3. the tool's read permission re-checked against the caller's role (denials audited);
4. ``store_id``, ``as_of`` and the user injected from the request, never from the model;
5. the handler runs in its own ``READ ONLY`` transaction with a statement timeout;
6. rows and serialized size capped (``truncated`` says so);
7. one ``ToolCallRecord`` per call, persisted with the turn as ``ai_tool_call``.

Results also feed the turn's evidence ledger.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg.errors
from pydantic import ValidationError
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.ai.ledger import EvidenceLedger
from app.domains.ai.models import ToolCallOrigin, ToolCallStatus
from app.domains.ai.tools import exception_tools, insight_tools, order_tools, product_tools
from app.domains.ai.tools.base import (
    ToolArgs,
    ToolContext,
    ToolError,
    ToolOutput,
    ToolSpec,
    as_json,
)
from app.domains.identity.service import StoreContext

logger = logging.getLogger("app.ai.tools")

CATALOG_ORDER = (
    "get_dashboard_summary",
    "list_exceptions",
    "get_exception",
    "get_exception_history",
    "get_related_orders",
    "get_product",
    "get_inventory_position",
    "get_inventory_movements",
    "get_overdue_orders",
    "get_import_errors",
    "get_operational_trends",
)
_ALL_SPECS = {
    spec.name: spec
    for spec in (
        *exception_tools.SPECS,
        *order_tools.SPECS,
        *product_tools.SPECS,
        *insight_tools.SPECS,
    )
}
TOOLS: dict[str, ToolSpec] = {name: _ALL_SPECS[name] for name in CATALOG_ORDER}
assert set(TOOLS) == set(_ALL_SPECS), "every implemented tool must be in the catalog order"

_LONG_STRING = 200  # strings are cut to this first when a result exceeds the byte cap
_ARGUMENTS_MAX_BYTES = 2_000


def compact(value: Any) -> Any:
    """Drop null fields recursively (compact tool results, PROMPT_DESIGN.md §1)."""
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def dumps(value: Any) -> str:
    """Serializer for tool results sent to a model: sorted keys, no whitespace, escaped text."""
    return json.dumps(compact(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _shorten(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _LONG_STRING:
        return value[: _LONG_STRING - 1] + "…"
    if isinstance(value, dict):
        return {k: _shorten(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_shorten(v) for v in value]
    return value


@dataclass
class ToolCallRecord:
    """Buffered metadata of one call; written to ``ai_tool_call`` at the end of the turn."""

    id: uuid.UUID
    sequence: int
    tool_name: str
    origin: ToolCallOrigin
    arguments: dict[str, Any]
    status: ToolCallStatus
    row_count: int | None
    duration_ms: int
    error: str | None
    result_refs: list[str] = field(default_factory=list)
    truncated: bool = False

    def summary(self) -> str:
        return json.dumps(
            {
                "row_count": self.row_count,
                "truncated": self.truncated,
                "refs": len(self.result_refs),
            },
            sort_keys=True,
        )


@dataclass(frozen=True)
class DeniedCall:
    tool_name: str
    missing: tuple[str, ...]


def _error_envelope(name: str, status: ToolCallStatus, message: str) -> dict[str, Any]:
    return {
        "tool": name,
        "status": status.value,
        "error": {"code": status.value, "message": message},
    }


def _validation_message(err: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}" for e in err.errors()
    ]
    return "; ".join(parts)[:400]


def _safe_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return {}
    try:
        encoded = json.dumps(arguments, default=str)
    except (TypeError, ValueError):
        return {}
    return arguments if len(encoded) <= _ARGUMENTS_MAX_BYTES else {"truncated": True}


class TurnTools:
    """Executes tool calls for one turn and keeps its evidence ledger and call log."""

    def __init__(
        self,
        bind: Engine | Connection,
        store: StoreContext,
        *,
        as_of: datetime,
        settings: Settings,
    ) -> None:
        self._bind = bind
        self.store = store
        self.as_of = as_of
        self._settings = settings
        self.ledger = EvidenceLedger()
        self.calls: list[ToolCallRecord] = []
        self.denied: list[DeniedCall] = []
        self._results: dict[str, dict[str, Any]] = {}

    # --- what the model may see ----------------------------------------------------------------

    def permitted_specs(self) -> list[ToolSpec]:
        """Tools offered to a model: only those the caller holds the base permission for."""
        return [spec for spec in TOOLS.values() if spec.permission in self.store.permissions]

    @property
    def remaining_calls(self) -> int:
        return max(self._settings.ai_max_tool_calls_per_turn - len(self.calls), 0)

    # --- execution -----------------------------------------------------------------------------

    def execute(self, name: str, arguments: Any, origin: ToolCallOrigin) -> dict[str, Any]:
        """Run one call and return its result envelope (success or failure). Identical successful
        calls in the same turn reuse the first result instead of running again."""
        call_id = uuid.uuid4()
        started = time.perf_counter()

        def fail(status: ToolCallStatus, message: str, recorded: Any) -> dict[str, Any]:
            return self._fail(call_id, name, origin, recorded, status, message, started)

        spec = TOOLS.get(name)
        args: ToolArgs | None = None
        invalid_message = ""
        if spec is not None:
            try:
                args = spec.args_model.model_validate(arguments if arguments is not None else {})
            except ValidationError as err:
                invalid_message = _validation_message(err)
        recorded = args.model_dump(mode="json", exclude_unset=True) if args else arguments
        cache_key = f"{name}:{json.dumps(recorded, sort_keys=True, default=str)}"
        if args is not None and cache_key in self._results:
            return self._results[cache_key]
        if not self.remaining_calls:
            return fail(
                ToolCallStatus.REJECTED_LIMIT,
                "The tool-call limit for this turn has been reached.",
                recorded,
            )
        if spec is None:
            return fail(ToolCallStatus.UNKNOWN_TOOL, "This tool does not exist.", arguments)
        if args is None:
            return fail(ToolCallStatus.INVALID_ARGUMENTS, invalid_message, arguments)
        missing = tuple(
            p.value for p in spec.required_permissions(args) if p not in self.store.permissions
        )
        if missing:
            self.denied.append(DeniedCall(name, missing))
            return fail(
                ToolCallStatus.PERMISSION_DENIED,
                "Your role does not allow reading this data.",
                recorded,
            )

        ctx = ToolContext(
            store=self.store,
            as_of=self.as_of,
            call_id=call_id,
            max_rows=self._settings.ai_tool_max_rows,
        )
        try:
            output = self._run(spec, ctx, args)
        except ToolError as err:
            return fail(err.status, err.message, recorded)
        except DBAPIError as err:
            if isinstance(err.orig, psycopg.errors.QueryCanceled):
                return fail(ToolCallStatus.TIMEOUT, "The query took too long.", recorded)
            logger.exception("ai_tool_db_error", extra={"tool": name})
            return fail(ToolCallStatus.ERROR, "The data could not be read.", recorded)
        except Exception:
            logger.exception("ai_tool_error", extra={"tool": name})
            return fail(ToolCallStatus.ERROR, "The data could not be read.", recorded)

        envelope = self._envelope(spec, ctx, output)
        self.ledger.add_envelope(envelope, envelope.get("result_ref"))
        refs = [
            f"{r['ref']['type']}:{r['ref']['id']}"
            for r in envelope["records"]
            if isinstance(r.get("ref"), dict)
        ]
        self._record(
            ToolCallRecord(
                id=call_id,
                sequence=len(self.calls),
                tool_name=name,
                origin=origin,
                arguments=recorded,
                status=ToolCallStatus.SUCCESS,
                row_count=envelope["row_count"],
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=None,
                result_refs=refs[:50],
                truncated=bool(envelope["truncated"]),
            )
        )
        self._results[cache_key] = envelope
        return envelope

    def _run(self, spec: ToolSpec, ctx: ToolContext, args: ToolArgs) -> ToolOutput:
        """The handler in its own read-only transaction: a bug that tried to write would fail at
        the database, and a slow query is cancelled by the statement timeout."""
        timeout_ms = int(self._settings.ai_tool_timeout_seconds * 1000)
        with Session(bind=self._bind, autoflush=False, expire_on_commit=False) as session:
            try:
                session.execute(text("SET TRANSACTION READ ONLY"))
                session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
                return spec.handler(session, ctx, args)
            finally:
                session.rollback()

    def _envelope(self, spec: ToolSpec, ctx: ToolContext, output: ToolOutput) -> dict[str, Any]:
        cap = min(spec.row_cap, ctx.max_rows)
        records: list[dict[str, Any]] = as_json(output.records[:cap])
        total = (
            output.total_available if output.total_available is not None else len(output.records)
        )
        truncated = output.truncated or len(output.records) > cap or total > len(records)
        envelope: dict[str, Any] = {
            "tool": spec.name,
            "status": ToolCallStatus.SUCCESS.value,
            "as_of": as_json(ctx.as_of),
            "data_window": {"from": as_json(output.data_window_from), "to": as_json(ctx.as_of)},
            "row_count": len(records),
            "total_available": total,
            "truncated": truncated,
            "untrusted_fields": output.untrusted_fields,
            "notes": output.notes,
            "result_ref": ctx.aggregate_ref(f"{spec.name} result"),
            **as_json(output.extra),
            "records": records,
        }
        limit = self._settings.ai_tool_max_result_bytes
        if len(dumps(envelope).encode()) > limit:
            envelope["records"] = records = _shorten(records)
            envelope["truncated"] = True
            while records and len(dumps(envelope).encode()) > limit:
                records.pop()
            envelope["row_count"] = len(records)
        return envelope

    def _fail(
        self,
        call_id: uuid.UUID,
        name: str,
        origin: ToolCallOrigin,
        arguments: Any,
        status: ToolCallStatus,
        message: str,
        started: float,
    ) -> dict[str, Any]:
        self._record(
            ToolCallRecord(
                id=call_id,
                sequence=len(self.calls),
                tool_name=name[:64],
                origin=origin,
                arguments=_safe_arguments(arguments),
                status=status,
                row_count=None,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=f"{status.value}: {message}"[:500],
            )
        )
        return _error_envelope(name, status, message)

    def _record(self, call: ToolCallRecord) -> None:
        # Rejected calls are recorded too, but a model flooding one round cannot grow the log
        # without bound.
        if len(self.calls) >= 2 * self._settings.ai_max_tool_calls_per_turn:
            return
        self.calls.append(call)
        logger.info(
            "ai_tool_call",
            extra={
                "tool": call.tool_name,
                "status": call.status.value,
                "origin": call.origin.value,
                "row_count": call.row_count,
                "duration_ms": call.duration_ms,
                "store_id": str(self.store.store_id),
            },
        )
