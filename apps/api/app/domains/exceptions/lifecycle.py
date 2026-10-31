"""Exception lifecycle rules (STATE_MACHINES.md §3.2). Pure functions, no I/O.

The service layer loads the exception, asks ``check_action`` whether the caller may perform an
action, applies the change, and records events and audit rows. The same checks produce the
``available_actions`` of the detail response, so the UI never has to guess.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core.errors import (
    AppError,
    BusinessRuleViolationError,
    ConflictError,
    PermissionDeniedError,
)
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    MANUAL_RESOLUTION_CODES,
    ExceptionStatus,
    ResolutionCode,
)
from app.domains.identity.permissions import Permission

S = ExceptionStatus

TRANSITIONS: dict[ExceptionStatus, frozenset[ExceptionStatus]] = {
    S.OPEN: frozenset({S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED, S.DISMISSED}),
    S.ACKNOWLEDGED: frozenset({S.IN_PROGRESS, S.RESOLVED, S.DISMISSED}),
    S.IN_PROGRESS: frozenset({S.RESOLVED, S.DISMISSED}),
    S.REOPENED: frozenset({S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED, S.DISMISSED}),
    S.RESOLVED: frozenset({S.REOPENED}),
    S.DISMISSED: frozenset({S.REOPENED}),
}

# Minimum length of resolution and dismissal notes, counted in non-whitespace characters.
CLOSING_NOTE_MIN_CHARS = 10
NOTE_MAX_CHARS = 4000


class ExceptionAction(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    START = "start"
    RESOLVE = "resolve"
    DISMISS = "dismiss"
    REOPEN = "reopen"
    ASSIGN = "assign"  # assign, reassign or unassign anyone (exceptions.assign)
    CLAIM = "claim"  # assign an unassigned exception to oneself (exceptions.work)
    ADD_NOTE = "add_note"
    SET_DUE_DATE = "set_due_date"


ACTION_TARGET: dict[ExceptionAction, ExceptionStatus] = {
    ExceptionAction.ACKNOWLEDGE: S.ACKNOWLEDGED,
    ExceptionAction.START: S.IN_PROGRESS,
    ExceptionAction.RESOLVE: S.RESOLVED,
    ExceptionAction.DISMISS: S.DISMISSED,
    ExceptionAction.REOPEN: S.REOPENED,
}

ACTION_PERMISSION: dict[ExceptionAction, Permission] = {
    ExceptionAction.ACKNOWLEDGE: Permission.EXCEPTIONS_WORK,
    ExceptionAction.START: Permission.EXCEPTIONS_WORK,
    ExceptionAction.RESOLVE: Permission.EXCEPTIONS_WORK,
    ExceptionAction.DISMISS: Permission.EXCEPTIONS_MANAGE,
    ExceptionAction.REOPEN: Permission.EXCEPTIONS_MANAGE,
    ExceptionAction.ASSIGN: Permission.EXCEPTIONS_ASSIGN,
    ExceptionAction.CLAIM: Permission.EXCEPTIONS_WORK,
    ExceptionAction.ADD_NOTE: Permission.EXCEPTIONS_WORK,
    ExceptionAction.SET_DUE_DATE: Permission.EXCEPTIONS_ASSIGN,
}

# Actions that only make sense while the exception is active.
_ACTIVE_ONLY = frozenset(
    {ExceptionAction.ASSIGN, ExceptionAction.CLAIM, ExceptionAction.SET_DUE_DATE}
)


class TransitionNotAllowedError(ConflictError):
    code = "EXCEPTION_TRANSITION_NOT_ALLOWED"


class StaleVersionError(ConflictError):
    code = "STALE_VERSION"


@dataclass(frozen=True)
class Actor:
    user_id: uuid.UUID
    permissions: frozenset[Permission]

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


@dataclass(frozen=True)
class ExceptionState:
    """The parts of an exception the lifecycle rules depend on."""

    status: ExceptionStatus
    assignee_id: uuid.UUID | None
    resolution_code: ResolutionCode | None = None
    # Another active exception with the same dedup key (a newer occurrence), if any.
    active_occurrence_id: uuid.UUID | None = None
    active_occurrence_reference: str | None = None


@dataclass(frozen=True)
class Denial:
    """Why an action is not allowed. ``kind`` is PERMISSION, OWNERSHIP or STATE."""

    kind: str
    status_code: int
    code: str
    message: str
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_error(self) -> AppError:
        if self.status_code == 403:
            return PermissionDeniedError(self.message, code=self.code, details=self.details)
        if self.code == TransitionNotAllowedError.code:
            return TransitionNotAllowedError(self.message, details=self.details)
        return ConflictError(self.message, code=self.code, details=self.details)


def allowed_transitions(status: ExceptionStatus) -> list[ExceptionStatus]:
    """Targets reachable from ``status``, in lifecycle order."""
    return [target for target in ExceptionStatus if target in TRANSITIONS[status]]


def can_transition(current: ExceptionStatus, target: ExceptionStatus) -> bool:
    return target in TRANSITIONS[current]


def _transition_denial(state: ExceptionState, target: ExceptionStatus, reason: str) -> Denial:
    return Denial(
        kind="STATE",
        status_code=409,
        code=TransitionNotAllowedError.code,
        message=reason,
        details=[
            {
                "current_status": state.status.value,
                "requested_status": target.value,
                "allowed_transitions": [s.value for s in allowed_transitions(state.status)],
            }
        ],
    )


def check_action(action: ExceptionAction, state: ExceptionState, actor: Actor) -> Denial | None:
    """Return why ``actor`` may not perform ``action`` on an exception in ``state``, or None.

    Order: role permission (403), lifecycle state (409), then ownership rules (403).
    """
    required = ACTION_PERMISSION[action]
    if not actor.can(required):
        return Denial(
            "PERMISSION",
            403,
            "PERMISSION_DENIED",
            "Your role does not allow this action.",
            [{"missing_permission": required.value}],
        )

    target = ACTION_TARGET.get(action)
    if target is not None and not can_transition(state.status, target):
        return _transition_denial(
            state, target, f"An exception in {state.status.value} cannot move to {target.value}."
        )
    if action in _ACTIVE_ONLY and state.status not in ACTIVE_STATUSES:
        return Denial(
            "STATE",
            409,
            "EXCEPTION_NOT_ACTIVE",
            f"This action needs an active exception; it is {state.status.value}.",
            [{"current_status": state.status.value}],
        )

    if action is ExceptionAction.REOPEN:
        if state.resolution_code is ResolutionCode.SUPERSEDED:
            return _transition_denial(
                state,
                S.REOPENED,
                "A superseded exception is final. Work on the exception that superseded it.",
            )
        if state.active_occurrence_id is not None:
            return Denial(
                "STATE",
                409,
                "EXCEPTION_NEWER_OCCURRENCE_EXISTS",
                "A newer occurrence of this condition is already active.",
                [
                    {
                        "exception_id": str(state.active_occurrence_id),
                        "reference": state.active_occurrence_reference,
                    }
                ],
            )

    is_assignee = state.assignee_id is not None and state.assignee_id == actor.user_id
    can_override = actor.can(Permission.EXCEPTIONS_ASSIGN) or actor.can(
        Permission.EXCEPTIONS_MANAGE
    )
    if (
        action is ExceptionAction.START
        and state.assignee_id is not None
        and not is_assignee
        and not can_override
    ):
        return Denial(
            "OWNERSHIP",
            403,
            "ASSIGNED_TO_ANOTHER_USER",
            "This exception is assigned to another user.",
        )
    if (
        action is ExceptionAction.RESOLVE
        and not is_assignee
        and not actor.can(Permission.EXCEPTIONS_MANAGE)
    ):
        return Denial(
            "OWNERSHIP",
            403,
            "NOT_ASSIGNEE",
            "Only the assignee or a manager can resolve this exception."
            + (" Claim it first." if state.assignee_id is None else ""),
        )
    if action is ExceptionAction.CLAIM and state.assignee_id is not None:
        if is_assignee:
            return Denial(
                "STATE", 409, "ALREADY_ASSIGNED", "This exception is already assigned to you."
            )
        return Denial(
            "OWNERSHIP",
            403,
            "ASSIGNED_TO_ANOTHER_USER",
            "Only an unassigned exception can be claimed. Ask a manager to reassign it.",
        )
    return None


@dataclass(frozen=True)
class BlockedAction:
    action: ExceptionAction
    code: str
    reason: str


def available_actions(
    state: ExceptionState, actor: Actor
) -> tuple[list[ExceptionAction], list[BlockedAction]]:
    """Actions the caller may perform now, and those blocked by permission or ownership.

    Actions that the lifecycle state rules out are omitted from both lists.
    """
    allowed: list[ExceptionAction] = []
    blocked: list[BlockedAction] = []
    unrestricted = Actor(actor.user_id, frozenset(Permission))
    for action in ExceptionAction:
        if check_action(action, state, unrestricted) is not None:
            continue  # not possible in this state for anyone
        denial = check_action(action, state, actor)
        if denial is None:
            allowed.append(action)
        elif denial.kind != "STATE":
            blocked.append(BlockedAction(action, denial.code, denial.message))
    return allowed, blocked


def non_whitespace_length(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def validate_closing_note(note: str | None, field_name: str) -> str:
    """Resolution and dismissal notes need ≥ 10 non-whitespace characters (422 otherwise)."""
    text = (note or "").strip()
    if non_whitespace_length(text) < CLOSING_NOTE_MIN_CHARS:
        raise BusinessRuleViolationError(
            f"The note must contain at least {CLOSING_NOTE_MIN_CHARS} non-whitespace characters.",
            code="VALIDATION_FAILED",
            details=[{"loc": ["body", field_name], "message": "note too short"}],
        )
    if len(text) > NOTE_MAX_CHARS:
        raise BusinessRuleViolationError(
            f"The note must be at most {NOTE_MAX_CHARS} characters.",
            code="VALIDATION_FAILED",
            details=[{"loc": ["body", field_name], "message": "note too long"}],
        )
    return text


def validate_resolution_code(code: ResolutionCode) -> ResolutionCode:
    """Users may only use the manual resolution codes; system codes are reserved."""
    if code not in MANUAL_RESOLUTION_CODES:
        raise BusinessRuleViolationError(
            f"{code.value} is set by the system and cannot be used for a manual resolution.",
            code="VALIDATION_FAILED",
            details=[{"loc": ["body", "resolution_code"], "message": "not a manual code"}],
        )
    return code
