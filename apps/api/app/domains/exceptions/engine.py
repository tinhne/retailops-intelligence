"""Exception evaluation entry point (EXCEPTION_CATALOG.md, STATE_MACHINES.md §3.3).

``run_evaluation`` is the contract used by imports, the manual trigger and the scheduler:

1. Take a transaction-level advisory lock for the store. If another evaluation holds it, record a
   ``SKIPPED`` run and return.
2. Record a ``RUNNING`` run, load the read-only snapshot, run the selected rules (pure functions)
   and reconcile their findings against stored exceptions, row by row of §3.3.
3. Rule or reconciliation errors never reach the caller: the work runs in a savepoint that is
   rolled back, and the run is stored as ``FAILED`` with a short message.

The caller commits (which also releases the advisory lock).

``version`` (optimistic concurrency) moves only when an exception event is written. Quiet
refreshes such as ``last_detected_at`` or the time component of priority are written with plain
UPDATE statements that leave ``version`` alone, so open detail pages do not go stale every run.
"""

import logging
import time
import uuid
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, or_, select, text, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.clock import utcnow
from app.domains.exceptions import repository
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    ActorType,
    EntityType,
    EvaluationRun,
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionAssignment,
    ExceptionEntityLink,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionStatus,
    ExceptionType,
    LinkRole,
    OperationalException,
    ResolutionCode,
)
from app.domains.exceptions.priority import (
    PriorityInputs,
    PriorityResult,
    PriorityWeights,
    compute_due_at,
    compute_priority,
)
from app.domains.exceptions.rules.base import Finding, Rule, jsonable, material_view
from app.domains.exceptions.rules.registry import SUPERSEDES, select_rules
from app.domains.exceptions.snapshot import EvaluationSnapshot, RuleSettings, load_settings
from app.domains.exceptions.snapshot import load_snapshot as load_evaluation_snapshot

logger = logging.getLogger("app.exceptions.engine")

EVALUATION_LOCK_NAMESPACE = 0x45564C31  # "EVL1": first key of the two-integer advisory lock

VERIFICATION_GRACE_HOURS = 24
"""Hours after a manual resolution after which a still-present condition reopens it.

A user-resolved exception whose condition is still detected is reopened (``VERIFICATION_FAILED``)
only when the data has been refreshed since the resolution (an import completed with
``applied_at > resolved_at``) or when this many hours have passed. Before that the evaluation may
be looking at data that predates the fix, so the exception stays ``RESOLVED`` and waits.
"""

SKIPPED_MESSAGE = "Another evaluation is running for this store."
COUNT_KEYS = ("created", "refreshed", "resolved", "verified", "reopened", "superseded", "unchanged")
_SUPERSEDE_CHAIN_LIMIT = 20

E = OperationalException


def advisory_lock_key(store_id: uuid.UUID) -> int:
    """32-bit signed key derived from the store UUID. Collisions only serialize two stores."""
    return int.from_bytes(store_id.bytes[:4], "big", signed=True)


def try_lock_store(db: Session, store_id: uuid.UUID) -> bool:
    acquired = db.execute(
        text("SELECT pg_try_advisory_xact_lock(CAST(:ns AS integer), CAST(:key AS integer))"),
        {"ns": EVALUATION_LOCK_NAMESPACE, "key": advisory_lock_key(store_id)},
    ).scalar_one()
    return bool(acquired)


def run_evaluation(
    db: Session,
    store_id: uuid.UUID,
    *,
    trigger: EvaluationTrigger,
    as_of: datetime,
    triggered_by: uuid.UUID | None = None,
    import_id: uuid.UUID | None = None,
    rule_ids: list[str] | None = None,
) -> EvaluationRun:
    """Evaluate rules for one store as of ``as_of`` and reconcile exceptions. Caller commits.

    Raises ``UnknownRuleError`` (422) for unknown ``rule_ids``; every other failure is recorded on
    the returned run instead of being raised.
    """
    rules = select_rules(rule_ids)
    rule_list = [rule.rule_id for rule in rules]
    # Wall-clock timestamps are run telemetry only; detection uses ``as_of`` (BR-504).
    started_at = utcnow()
    started = time.perf_counter()

    if not try_lock_store(db, store_id):
        run = EvaluationRun(
            store_id=store_id,
            trigger=trigger,
            status=EvaluationStatus.SKIPPED,
            as_of=as_of,
            rules=rule_list,
            counts={},
            started_at=started_at,
            finished_at=started_at,
            duration_ms=0,
            triggered_by=triggered_by,
            import_id=import_id,
            error=SKIPPED_MESSAGE,
        )
        db.add(run)
        db.flush()
        logger.info(
            "evaluation_skipped",
            extra={"store_id": str(store_id), "evaluation_run_id": str(run.id)},
        )
        return run

    run = EvaluationRun(
        store_id=store_id,
        trigger=trigger,
        status=EvaluationStatus.RUNNING,
        as_of=as_of,
        rules=rule_list,
        counts={},
        started_at=started_at,
        triggered_by=triggered_by,
        import_id=import_id,
    )
    db.add(run)
    db.flush()
    run_id = run.id

    counts: dict[str, int] | None = None
    error: str | None = None
    try:
        with db.begin_nested():
            counts = _evaluate(db, store_id, run_id, rules, as_of)
    except Exception as exc:
        logger.exception(
            "evaluation_failed",
            extra={"store_id": str(store_id), "evaluation_run_id": str(run_id)},
        )
        # In-memory state may describe rolled-back rows; reload everything from the database.
        db.expire_all()
        error = _short_error(exc)

    run.finished_at = utcnow()
    run.duration_ms = int((time.perf_counter() - started) * 1000)
    if counts is None:
        run.status = EvaluationStatus.FAILED
        run.error = error
        run.counts = {}
    else:
        run.status = EvaluationStatus.SUCCEEDED
        run.counts = counts
    db.flush()
    logger.info(
        "evaluation_finished",
        extra={
            "store_id": str(store_id),
            "evaluation_run_id": str(run_id),
            "status": run.status.value,
            "counts": run.counts,
            "duration_ms": run.duration_ms,
        },
    )
    return run


def _short_error(exc: Exception) -> str:
    """A short, safe message for the run row. Database errors never expose SQL."""
    if isinstance(exc, SQLAlchemyError):
        origin = type(getattr(exc, "orig", None) or exc).__name__
        return f"Database error during evaluation ({origin})."
    message = str(exc).splitlines()[0] if str(exc) else ""
    return f"{type(exc).__name__}: {message}"[:300]


def _evaluate(
    db: Session,
    store_id: uuid.UUID,
    run_id: uuid.UUID,
    rules: tuple[Rule, ...],
    as_of: datetime,
) -> dict[str, int]:
    settings = load_settings(db, store_id)
    snapshot = load_evaluation_snapshot(db, store_id, as_of, settings)
    findings: list[Finding] = []
    for rule in rules:
        findings.extend(rule.evaluate(snapshot, settings, as_of))
    reconciler = _Reconciler(db, store_id, run_id, as_of, settings, snapshot)
    return reconciler.reconcile(findings, {rule.exception_type for rule in rules})


class _Reconciler:
    """Applies the STATE_MACHINES.md §3.3 table for one run."""

    def __init__(
        self,
        db: Session,
        store_id: uuid.UUID,
        run_id: uuid.UUID,
        as_of: datetime,
        settings: RuleSettings,
        snapshot: EvaluationSnapshot,
    ) -> None:
        self.db = db
        self.store_id = store_id
        self.run_id = run_id
        self.as_of = as_of
        self.settings = settings
        self.snapshot = snapshot
        self.weights = PriorityWeights.from_settings(settings.priority_weights)
        self.counts: Counter[str] = Counter()

        self.by_id: dict[uuid.UUID, OperationalException] = {}
        self.latest: dict[str, OperationalException] = {}
        self.created: list[OperationalException] = []
        self.created_ids: set[uuid.UUID] = set()
        self.changes: dict[uuid.UUID, dict[str, Any]] = {}
        self.bumped: set[uuid.UUID] = set()
        self.events: list[ExceptionEvent] = []
        self.assignments: list[ExceptionAssignment] = []
        self.handled: set[uuid.UUID] = set()
        # key → the active exception that represents the finding after this run
        self.result: dict[str, OperationalException] = {}
        self.touched: list[tuple[OperationalException, Finding]] = []
        self._eligible: set[uuid.UUID] | None = None

    # --- entry point ---------------------------------------------------------------------------

    def reconcile(self, findings: list[Finding], ran_types: set[ExceptionType]) -> dict[str, int]:
        by_key: dict[str, Finding] = {}
        for finding in findings:
            if finding.dedup_key in by_key:
                raise ValueError(f"Duplicate finding for {finding.dedup_key}")
            by_key[finding.dedup_key] = finding

        self._load(by_key, ran_types)
        for finding in findings:
            self._apply_finding(finding)
        for finding in findings:
            self._supersede_for(finding)
        self._apply_absent(by_key, ran_types)
        self._recompute_priorities()
        self._write()
        return {key: int(self.counts.get(key, 0)) for key in COUNT_KEYS}

    # --- loading -------------------------------------------------------------------------------

    def _lock_load(self, condition: Any) -> list[OperationalException]:
        rows = self.db.scalars(
            select(E)
            .where(E.store_id == self.store_id, condition)
            .order_by(E.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        for row in rows:
            self.by_id[row.id] = row
        return list(rows)

    def _load(self, by_key: dict[str, Finding], ran_types: set[ExceptionType]) -> None:
        active = self._lock_load(E.status.in_(ACTIVE_STATUSES))
        for exc in active:
            self.latest[exc.dedup_key] = exc

        pending_keys = set(
            self.db.scalars(
                select(E.dedup_key).where(
                    E.store_id == self.store_id,
                    E.exception_type.in_(ran_types),
                    or_(
                        and_(
                            E.status == ExceptionStatus.RESOLVED,
                            E.resolution_actor == ActorType.USER,
                            E.verified_at.is_(None),
                        ),
                        and_(
                            E.status == ExceptionStatus.DISMISSED,
                            E.condition_cleared_at.is_(None),
                        ),
                    ),
                )
            ).all()
        )
        keys = (set(by_key) | pending_keys) - set(self.latest)
        if not keys:
            return
        latest_ids = (
            select(E.id)
            .where(E.store_id == self.store_id, E.dedup_key.in_(keys))
            .order_by(E.dedup_key, E.first_detected_at.desc(), E.created_at.desc(), E.id.desc())
            .ext(distinct_on(E.dedup_key))
        )
        for exc in self._lock_load(E.id.in_(latest_ids)):
            self.latest[exc.dedup_key] = exc

    # --- per-finding outcomes ------------------------------------------------------------------

    def _apply_finding(self, finding: Finding) -> None:
        key = finding.dedup_key
        latest = self.latest.get(key)
        if latest is None:
            self._create(finding, previous=None)
            return
        self.handled.add(latest.id)
        status = latest.status
        if status in ACTIVE_STATUSES:
            self._refresh(latest, finding)
        elif status is ExceptionStatus.RESOLVED:
            self._present_after_resolution(latest, finding)
        elif latest.condition_cleared_at is None:
            # DISMISSED and the condition never cleared: last_detected_at only, no event.
            self._set(latest, last_detected_at=self.as_of)
            self.counts["unchanged"] += 1
        else:
            # DISMISSED, cleared since, and detected again: a new occurrence.
            self._create(finding, previous=latest)

    def _present_after_resolution(self, latest: OperationalException, finding: Finding) -> None:
        assert latest.resolved_at is not None
        if latest.resolution_code is ResolutionCode.SUPERSEDED:
            # Superseded is final: the returning condition is a new occurrence.
            self._create(finding, previous=latest)
        elif latest.resolution_actor is ActorType.USER and latest.verified_at is None:
            if self._verification_due(latest.resolved_at):
                self._reopen(latest, finding, "VERIFICATION_FAILED")
            else:
                self.counts["unchanged"] += 1  # awaiting verification after fresh data
        elif self.as_of - latest.resolved_at <= timedelta(hours=self.settings.reopen_window_hours):
            self._reopen(latest, finding, "RECURRED_WITHIN_WINDOW")
        else:
            self._create(finding, previous=latest)

    def _verification_due(self, resolved_at: datetime) -> bool:
        refreshed = self.snapshot.last_import_applied_at
        if refreshed is not None and refreshed > resolved_at:
            return True
        return self.as_of - resolved_at >= timedelta(hours=VERIFICATION_GRACE_HOURS)

    def _create(self, finding: Finding, previous: OperationalException | None) -> None:
        exc_id = uuid.uuid4()
        priority = self._priority(finding, first_detected_at=self.as_of)
        due = compute_due_at(finding.severity, self.as_of, finding.deadline_at)
        assignee, carried_from = self._carry_over_for_new(finding, previous)
        exc = OperationalException(
            id=exc_id,
            store_id=self.store_id,
            reference=repository.allocate_reference(self.db, self.store_id),
            exception_type=finding.exception_type,
            category=finding.category,
            rule_id=finding.rule_id,
            dedup_key=finding.dedup_key,
            primary_entity_type=finding.primary_entity.type,
            primary_entity_id=finding.primary_entity.id,
            status=ExceptionStatus.OPEN,
            severity=finding.severity,
            priority_score=priority.score,
            priority_band=priority.band,
            priority_breakdown={**priority.breakdown, "due": due.as_json()},
            title=finding.title,
            evidence=finding.evidence,
            calculation=finding.calculation,
            recommended_action=finding.recommended_action,
            exposure_amount=finding.exposure_amount,
            affected_order_count=finding.affected_order_count,
            deadline_at=finding.deadline_at,
            due_at=due.due_at,
            due_at_overridden=False,
            assignee_id=assignee,
            first_detected_at=self.as_of,
            last_detected_at=self.as_of,
            detection_count=1,
            previous_occurrence_id=previous.id if previous else None,
            reopen_count=0,
            version=1,
        )
        self.created.append(exc)
        self.created_ids.add(exc_id)
        self.by_id[exc_id] = exc
        self.result[finding.dedup_key] = exc
        self.touched.append((exc, finding))
        self._event(
            exc,
            ExceptionEventType.DETECTED,
            to_status=ExceptionStatus.OPEN,
            payload={
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "priority_score": priority.score,
                "priority_band": priority.band,
                "due_at": due.due_at,
                "previous_occurrence_id": previous.id if previous else None,
                "previous_occurrence_reference": previous.reference if previous else None,
            },
        )
        if assignee is not None and carried_from is not None:
            self._record_assignment(exc, assignee, carried_from, previous_assignee=None)
        self.counts["created"] += 1

    def _refresh(self, exc: OperationalException, finding: Finding) -> None:
        events = self._apply_detection(exc, finding, recompute_due=not exc.due_at_overridden)
        self.result[finding.dedup_key] = exc
        self.touched.append((exc, finding))
        self.counts["refreshed" if events else "unchanged"] += 1

    def _reopen(self, exc: OperationalException, finding: Finding, reason: str) -> None:
        from_status = exc.status
        previous_resolution = {
            "status": exc.status,
            "resolved_at": exc.resolved_at,
            "resolved_by": exc.resolved_by,
            "resolution_actor": exc.resolution_actor,
            "resolution_code": exc.resolution_code,
            "resolution_note": exc.resolution_note,
            "verified_at": exc.verified_at,
        }
        due_before = exc.due_at
        # A reopened exception starts a new response cycle; a manual override is cleared.
        due = compute_due_at(finding.severity, self.as_of, finding.deadline_at)
        self._set(
            exc,
            status=ExceptionStatus.REOPENED,
            reopen_count=exc.reopen_count + 1,
            resolved_at=None,
            resolved_by=None,
            resolution_actor=None,
            resolution_code=None,
            resolution_note=None,
            verified_at=None,
            dismissed_reason=None,
            condition_cleared_at=None,
            due_at=due.due_at,
            due_at_overridden=False,
            priority_breakdown={**exc.priority_breakdown, "due": due.as_json()},
        )
        self._event(
            exc,
            ExceptionEventType.REOPENED,
            from_status=from_status,
            to_status=ExceptionStatus.REOPENED,
            payload={
                "reason": reason,
                "previous_resolution": previous_resolution,
                "due_date_changed": {
                    "from": due_before,
                    "to": due.due_at,
                    "basis": due.basis,
                    "override_cleared": True,
                },
            },
        )
        self._apply_detection(exc, finding, recompute_due=False, reopening=True)
        self.result[finding.dedup_key] = exc
        self.touched.append((exc, finding))
        self.counts["reopened"] += 1

    def _apply_detection(
        self,
        exc: OperationalException,
        finding: Finding,
        *,
        recompute_due: bool,
        reopening: bool = False,
    ) -> list[ExceptionEventType]:
        """Copy the finding onto a stored exception; write change events. Returns the events."""
        written: list[ExceptionEventType] = []
        material_changed = material_view(exc.evidence or {}) != material_view(finding.evidence)
        severity_before = exc.severity
        if material_changed:
            self._event(
                exc,
                ExceptionEventType.EVIDENCE_UPDATED,
                payload={
                    "previous": {
                        "title": exc.title,
                        "evidence": exc.evidence,
                        "calculation": exc.calculation,
                        "exposure_amount": exc.exposure_amount,
                        "affected_order_count": exc.affected_order_count,
                        "deadline_at": exc.deadline_at,
                    },
                    "changed_facts": _changed_facts(exc.evidence or {}, finding.evidence),
                },
            )
            written.append(ExceptionEventType.EVIDENCE_UPDATED)
        values: dict[str, Any] = {
            "rule_id": finding.rule_id,
            "category": finding.category,
            "title": finding.title,
            "evidence": finding.evidence,
            "calculation": finding.calculation,
            "recommended_action": finding.recommended_action,
            "exposure_amount": finding.exposure_amount,
            "affected_order_count": finding.affected_order_count,
            "deadline_at": finding.deadline_at,
            "severity": finding.severity,
            "last_detected_at": self.as_of,
            "detection_count": exc.detection_count + 1,
        }
        if finding.severity is not severity_before:
            payload: dict[str, Any] = {"from": severity_before, "to": finding.severity}
            if recompute_due:
                anchor = _due_anchor(exc)
                due = compute_due_at(finding.severity, anchor, finding.deadline_at)
                payload["due_at"] = {"from": exc.due_at, "to": due.due_at, "basis": due.basis}
                values["due_at"] = due.due_at
                values["priority_breakdown"] = {**exc.priority_breakdown, "due": due.as_json()}
            elif exc.due_at_overridden and not reopening:
                payload["due_at"] = {"from": exc.due_at, "to": exc.due_at, "basis": "OVERRIDE"}
            self._event(exc, ExceptionEventType.SEVERITY_CHANGED, payload=payload)
            written.append(ExceptionEventType.SEVERITY_CHANGED)
        self._set(exc, **values)
        return written

    # --- supersede -----------------------------------------------------------------------------

    def _lower_active(self, finding: Finding) -> list[OperationalException]:
        lower = SUPERSEDES.get(finding.exception_type, frozenset())
        if not lower:
            return []
        return sorted(
            (
                exc
                for exc in self.by_id.values()
                if exc.id not in self.created_ids
                and exc.status in ACTIVE_STATUSES
                and exc.exception_type in lower
                and exc.primary_entity_type is finding.primary_entity.type
                and exc.primary_entity_id == finding.primary_entity.id
            ),
            key=lambda exc: (exc.last_detected_at, exc.first_detected_at),
            reverse=True,
        )

    def _supersede_for(self, finding: Finding) -> None:
        target = self.result.get(finding.dedup_key)
        if target is None:
            return  # the finding maps to a dismissed or not-yet-verified exception
        for old in self._lower_active(finding):
            from_status = old.status
            self.handled.add(old.id)
            self._set(
                old,
                status=ExceptionStatus.RESOLVED,
                resolved_at=self.as_of,
                resolved_by=None,
                resolution_actor=ActorType.SYSTEM,
                resolution_code=ResolutionCode.SUPERSEDED,
                superseded_by_id=target.id,
            )
            self._event(
                old,
                ExceptionEventType.SUPERSEDED,
                from_status=from_status,
                to_status=ExceptionStatus.RESOLVED,
                payload={
                    "superseded_by_id": target.id,
                    "superseded_by_reference": target.reference,
                    "superseded_by_type": target.exception_type,
                },
            )
            self.counts["superseded"] += 1
            if (
                target.assignee_id is None
                and old.assignee_id is not None
                and old.assignee_id in self._eligible_ids()
            ):
                if target.id in self.created_ids:
                    target.assignee_id = old.assignee_id
                else:
                    self._set(target, assignee_id=old.assignee_id)
                self._record_assignment(target, old.assignee_id, old, previous_assignee=None)

    def _carry_over_for_new(
        self, finding: Finding, previous: OperationalException | None
    ) -> tuple[uuid.UUID | None, OperationalException | None]:
        """Assignee for a new exception (BR-401).

        From an active, less severe exception it supersedes; else, when the previous occurrence
        was superseded, from the most recent exception of that supersede chain. Only users who
        are still eligible assignees carry over.
        """
        eligible = self._eligible_ids()
        for old in self._lower_active(finding):
            if old.assignee_id is not None and old.assignee_id in eligible:
                return old.assignee_id, old
        if previous is not None and previous.resolution_code is ResolutionCode.SUPERSEDED:
            latest = self._end_of_supersede_chain(previous)
            if latest.assignee_id is not None and latest.assignee_id in eligible:
                return latest.assignee_id, latest
        return None, None

    def _end_of_supersede_chain(self, start: OperationalException) -> OperationalException:
        current = start
        seen = {start.id}
        for _ in range(_SUPERSEDE_CHAIN_LIMIT):
            next_id = current.superseded_by_id
            if next_id is None or next_id in seen:
                break
            nxt = self.by_id.get(next_id) or self.db.scalar(
                select(E).where(E.store_id == self.store_id, E.id == next_id)
            )
            if nxt is None:
                break
            seen.add(nxt.id)
            current = nxt
        return current

    def _eligible_ids(self) -> set[uuid.UUID]:
        if self._eligible is None:
            self._eligible = repository.eligible_assignee_ids(self.db, self.store_id)
        return self._eligible

    # --- absent findings -----------------------------------------------------------------------

    def _apply_absent(self, by_key: dict[str, Finding], ran_types: set[ExceptionType]) -> None:
        """Only rules that ran can resolve, verify or clear (STATE_MACHINES.md §3.3)."""
        for key, exc in sorted(self.latest.items()):
            if key in by_key or exc.id in self.handled or exc.exception_type not in ran_types:
                continue
            if exc.status in ACTIVE_STATUSES:
                from_status = exc.status
                self._set(
                    exc,
                    status=ExceptionStatus.RESOLVED,
                    resolved_at=self.as_of,
                    resolved_by=None,
                    resolution_actor=ActorType.SYSTEM,
                    resolution_code=ResolutionCode.CONDITION_CLEARED,
                    resolution_note=None,
                )
                self._event(
                    exc,
                    ExceptionEventType.AUTO_RESOLVED,
                    from_status=from_status,
                    to_status=ExceptionStatus.RESOLVED,
                    payload={"resolution_code": ResolutionCode.CONDITION_CLEARED},
                )
                self.counts["resolved"] += 1
            elif (
                exc.status is ExceptionStatus.RESOLVED
                and exc.resolution_actor is ActorType.USER
                and exc.verified_at is None
            ):
                self._set(exc, verified_at=self.as_of)
                self._event(
                    exc,
                    ExceptionEventType.VERIFIED,
                    payload={
                        "resolved_at": exc.resolved_at,
                        "resolution_code": exc.resolution_code,
                    },
                )
                self.counts["verified"] += 1
            elif exc.status is ExceptionStatus.DISMISSED and exc.condition_cleared_at is None:
                self._set(exc, condition_cleared_at=self.as_of)

    # --- priority ------------------------------------------------------------------------------

    def _priority_inputs(
        self, finding_or_exc: Finding | OperationalException, first_detected_at: datetime
    ) -> PriorityInputs:
        return PriorityInputs(
            severity=finding_or_exc.severity,
            affected_order_count=finding_or_exc.affected_order_count,
            exposure_amount=finding_or_exc.exposure_amount,
            deadline_at=finding_or_exc.deadline_at,
            first_detected_at=first_detected_at,
        )

    def _priority(self, finding: Finding, *, first_detected_at: datetime) -> PriorityResult:
        return compute_priority(
            self._priority_inputs(finding, first_detected_at),
            weights=self.weights,
            exposure_cap=self.settings.exposure_cap,
            as_of=self.as_of,
        )

    def _recompute_priorities(self) -> None:
        """Every active exception gets a fresh score so the age and deadline components move."""
        for exc in self.by_id.values():
            if exc.id in self.created_ids or exc.status not in ACTIVE_STATUSES:
                continue
            result = compute_priority(
                self._priority_inputs(exc, exc.first_detected_at),
                weights=self.weights,
                exposure_cap=self.settings.exposure_cap,
                as_of=self.as_of,
            )
            breakdown = dict(result.breakdown)
            if isinstance(exc.priority_breakdown, dict) and "due" in exc.priority_breakdown:
                breakdown["due"] = exc.priority_breakdown["due"]
            self._set(
                exc,
                priority_score=result.score,
                priority_band=result.band,
                priority_breakdown=breakdown,
            )

    # --- bookkeeping ---------------------------------------------------------------------------

    def _set(self, exc: OperationalException, **values: Any) -> None:
        if exc.id in self.created_ids:
            for name, value in values.items():
                setattr(exc, name, value)
            return
        self.changes.setdefault(exc.id, {}).update(values)
        for name, value in values.items():
            set_committed_value(exc, name, value)

    def _event(
        self,
        exc: OperationalException,
        event_type: ExceptionEventType,
        *,
        from_status: ExceptionStatus | None = None,
        to_status: ExceptionStatus | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            ExceptionEvent(
                exception_id=exc.id,
                store_id=self.store_id,
                event_type=event_type,
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                evaluation_run_id=self.run_id,
                from_status=from_status,
                to_status=to_status,
                payload=jsonable(payload or {}),
                occurred_at=self.as_of,
            )
        )
        if exc.id not in self.created_ids:
            self.bumped.add(exc.id)

    def _record_assignment(
        self,
        exc: OperationalException,
        assignee_id: uuid.UUID,
        carried_from: OperationalException,
        *,
        previous_assignee: uuid.UUID | None,
    ) -> None:
        self.assignments.append(
            ExceptionAssignment(
                exception_id=exc.id,
                assignee_id=assignee_id,
                assigned_by=None,
                assigned_at=self.as_of,
            )
        )
        self._event(
            exc,
            ExceptionEventType.ASSIGNED,
            payload={
                "assignee_id": assignee_id,
                "previous_assignee_id": previous_assignee,
                "reason": "CARRIED_OVER",
                "carried_over_from_id": carried_from.id,
                "carried_over_from_reference": carried_from.reference,
            },
        )

    def _write(self) -> None:
        db = self.db
        if self.created:
            db.add_all(self.created)
            db.flush()
        for exc_id, values in self.changes.items():
            exc = self.by_id[exc_id]
            if exc_id in self.bumped:
                values["version"] = exc.version + 1
            db.execute(
                update(E)
                .where(E.store_id == self.store_id, E.id == exc_id)
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if "version" in values:
                set_committed_value(exc, "version", values["version"])
            db.expire(exc, ["updated_at"])
        db.add_all(self.events)
        db.add_all(self.assignments)
        self._sync_links()
        db.flush()

    def _sync_links(self) -> None:
        if not self.touched:
            return
        desired: dict[uuid.UUID, dict[tuple[EntityType, uuid.UUID], LinkRole]] = {}
        for exc, finding in self.touched:
            wanted: dict[tuple[EntityType, uuid.UUID], LinkRole] = {
                (finding.primary_entity.type, finding.primary_entity.id): LinkRole.PRIMARY
            }
            for ref in finding.related_entities:
                wanted.setdefault((ref.type, ref.id), LinkRole.AFFECTED)
            desired[exc.id] = wanted
        existing = self.db.scalars(
            select(ExceptionEntityLink).where(
                ExceptionEntityLink.store_id == self.store_id,
                ExceptionEntityLink.exception_id.in_(list(desired)),
            )
        ).all()
        stale: list[uuid.UUID] = []
        present: dict[uuid.UUID, set[tuple[EntityType, uuid.UUID]]] = {}
        for link in existing:
            key = (link.entity_type, link.entity_id)
            role = desired[link.exception_id].get(key)
            if role is None:
                stale.append(link.id)
                continue
            if link.role is not role:
                link.role = role
            present.setdefault(link.exception_id, set()).add(key)
        if stale:
            self.db.execute(
                delete(ExceptionEntityLink)
                .where(
                    ExceptionEntityLink.store_id == self.store_id,
                    ExceptionEntityLink.id.in_(stale),
                )
                .execution_options(synchronize_session=False)
            )
        for exc_id, wanted in desired.items():
            have = present.get(exc_id, set())
            self.db.add_all(
                ExceptionEntityLink(
                    exception_id=exc_id,
                    store_id=self.store_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    role=role,
                )
                for (entity_type, entity_id), role in wanted.items()
                if (entity_type, entity_id) not in have
            )


def _due_anchor(exc: OperationalException) -> datetime:
    """The time the current response cycle started: reopen time, else first detection."""
    due = exc.priority_breakdown.get("due") if isinstance(exc.priority_breakdown, dict) else None
    if isinstance(due, dict) and isinstance(due.get("anchor_at"), str):
        try:
            return datetime.fromisoformat(due["anchor_at"])
        except ValueError:
            pass
    return exc.first_detected_at


def _changed_facts(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    before = material_view(old)["facts"]
    after = material_view(new)["facts"]
    keys: Iterable[str] = sorted(set(before) | set(after), key=str)
    changed = [key for key in keys if before.get(key) != after.get(key)]
    if material_view(old)["records"] != material_view(new)["records"]:
        changed.append("records")
    return changed
