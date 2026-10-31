"""Exception lifecycle transitions, actors and permissions (STATE_MACHINES.md §3.2)."""

import uuid

import pytest

from app.core.errors import BusinessRuleViolationError
from app.domains.exceptions.lifecycle import (
    TRANSITIONS,
    Actor,
    ExceptionAction,
    ExceptionState,
    available_actions,
    can_transition,
    check_action,
    validate_closing_note,
    validate_resolution_code,
)
from app.domains.exceptions.models import (
    MANUAL_RESOLUTION_CODES,
    ExceptionStatus,
    ResolutionCode,
)
from app.domains.exceptions.schemas import ManualResolutionCode
from app.domains.identity.permissions import Role, permissions_for

S = ExceptionStatus
A = ExceptionAction
ME = uuid.UUID(int=1)
OTHER = uuid.UUID(int=2)

EXPECTED: dict[ExceptionStatus, set[ExceptionStatus]] = {
    S.OPEN: {S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED, S.DISMISSED},
    S.ACKNOWLEDGED: {S.IN_PROGRESS, S.RESOLVED, S.DISMISSED},
    S.IN_PROGRESS: {S.RESOLVED, S.DISMISSED},
    S.REOPENED: {S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED, S.DISMISSED},
    S.RESOLVED: {S.REOPENED},
    S.DISMISSED: {S.REOPENED},
}


def actor(role: Role, user_id: uuid.UUID = ME) -> Actor:
    return Actor(user_id=user_id, permissions=permissions_for(role))


@pytest.mark.parametrize("current", list(S))
@pytest.mark.parametrize("target", list(S))
def test_transition_matrix_matches_state_machine(
    current: ExceptionStatus, target: ExceptionStatus
) -> None:
    """Every (from, to) pair of §3.2: allowed exactly when the diagram has the edge."""
    assert can_transition(current, target) is (target in EXPECTED[current])


def test_transition_table_covers_every_status() -> None:
    assert set(TRANSITIONS) == set(S)


@pytest.mark.parametrize(
    ("action", "status", "allowed"),
    [
        (A.ACKNOWLEDGE, S.OPEN, True),
        (A.ACKNOWLEDGE, S.REOPENED, True),  # REOPENED → ACKNOWLEDGED (O-30)
        (A.ACKNOWLEDGE, S.ACKNOWLEDGED, False),
        (A.ACKNOWLEDGE, S.IN_PROGRESS, False),
        (A.START, S.OPEN, True),
        (A.START, S.ACKNOWLEDGED, True),
        (A.START, S.REOPENED, True),
        (A.START, S.IN_PROGRESS, False),
        (A.START, S.RESOLVED, False),
        (A.RESOLVE, S.IN_PROGRESS, True),
        (A.RESOLVE, S.RESOLVED, False),
        (A.RESOLVE, S.DISMISSED, False),
        (A.DISMISS, S.OPEN, True),
        (A.DISMISS, S.IN_PROGRESS, True),
        (A.DISMISS, S.DISMISSED, False),
        (A.REOPEN, S.RESOLVED, True),
        (A.REOPEN, S.DISMISSED, True),
        (A.REOPEN, S.OPEN, False),
        (A.ASSIGN, S.RESOLVED, False),
        (A.SET_DUE_DATE, S.DISMISSED, False),
        (A.ADD_NOTE, S.RESOLVED, True),  # notes are allowed in any status
    ],
)
def test_manager_action_validity_by_status(
    action: ExceptionAction, status: ExceptionStatus, allowed: bool
) -> None:
    state = ExceptionState(status=status, assignee_id=ME)
    denial = check_action(action, state, actor(Role.MANAGER))
    assert (denial is None) is allowed
    if denial is not None:
        assert denial.status_code == 409


def test_invalid_transition_is_409_with_allowed_transitions_in_details() -> None:
    denial = check_action(A.START, ExceptionState(S.DISMISSED, None), actor(Role.MANAGER))
    assert denial is not None
    error = denial.to_error()
    assert (error.status_code, error.code) == (409, "EXCEPTION_TRANSITION_NOT_ALLOWED")
    assert error.details == [
        {
            "current_status": "DISMISSED",
            "requested_status": "IN_PROGRESS",
            "allowed_transitions": ["REOPENED"],
        }
    ]


@pytest.mark.parametrize(
    ("role", "action", "allowed"),
    [
        (Role.VIEWER, A.ACKNOWLEDGE, False),
        (Role.ANALYST, A.START, False),
        (Role.STAFF, A.ACKNOWLEDGE, True),
        (Role.STAFF, A.DISMISS, False),
        (Role.STAFF, A.SET_DUE_DATE, False),
        (Role.STAFF, A.ASSIGN, False),
        (Role.STAFF, A.CLAIM, True),
        (Role.STAFF, A.ADD_NOTE, True),
        (Role.MANAGER, A.DISMISS, True),
        (Role.MANAGER, A.ASSIGN, True),
        (Role.OWNER, A.SET_DUE_DATE, True),
    ],
)
def test_role_permissions_on_an_unassigned_open_exception(
    role: Role, action: ExceptionAction, allowed: bool
) -> None:
    denial = check_action(action, ExceptionState(S.OPEN, None), actor(role))
    assert (denial is None) is allowed
    if denial is not None:
        assert (denial.status_code, denial.code) == (403, "PERMISSION_DENIED")


def test_staff_may_start_only_unassigned_or_own_exceptions() -> None:
    staff = actor(Role.STAFF)
    assert check_action(A.START, ExceptionState(S.OPEN, None), staff) is None
    assert check_action(A.START, ExceptionState(S.OPEN, ME), staff) is None
    denial = check_action(A.START, ExceptionState(S.OPEN, OTHER), staff)
    assert denial is not None
    assert (denial.status_code, denial.code) == (403, "ASSIGNED_TO_ANOTHER_USER")
    # A manager may start work on someone else's exception (the assignee is kept).
    assert check_action(A.START, ExceptionState(S.OPEN, OTHER), actor(Role.MANAGER)) is None


def test_resolve_requires_assignee_or_manage_permission() -> None:
    staff = actor(Role.STAFF)
    assert check_action(A.RESOLVE, ExceptionState(S.IN_PROGRESS, ME), staff) is None
    for assignee in (OTHER, None):
        denial = check_action(A.RESOLVE, ExceptionState(S.IN_PROGRESS, assignee), staff)
        assert denial is not None
        assert (denial.status_code, denial.code) == (403, "NOT_ASSIGNEE")
    assert check_action(A.RESOLVE, ExceptionState(S.OPEN, OTHER), actor(Role.MANAGER)) is None


def test_claim_only_unassigned() -> None:
    staff = actor(Role.STAFF)
    taken = check_action(A.CLAIM, ExceptionState(S.OPEN, OTHER), staff)
    assert taken is not None
    assert taken.code == "ASSIGNED_TO_ANOTHER_USER"
    mine = check_action(A.CLAIM, ExceptionState(S.OPEN, ME), staff)
    assert mine is not None
    assert mine.code == "ALREADY_ASSIGNED"


def test_superseded_exception_cannot_be_reopened() -> None:
    state = ExceptionState(S.RESOLVED, None, resolution_code=ResolutionCode.SUPERSEDED)
    denial = check_action(A.REOPEN, state, actor(Role.MANAGER))
    assert denial is not None
    assert denial.code == "EXCEPTION_TRANSITION_NOT_ALLOWED"


def test_reopen_blocked_while_a_newer_occurrence_is_active() -> None:
    newer = uuid.uuid4()
    state = ExceptionState(
        S.DISMISSED, None, active_occurrence_id=newer, active_occurrence_reference="EXC-1009"
    )
    denial = check_action(A.REOPEN, state, actor(Role.MANAGER))
    assert denial is not None
    assert (denial.status_code, denial.code) == (409, "EXCEPTION_NEWER_OCCURRENCE_EXISTS")
    assert denial.details == [{"exception_id": str(newer), "reference": "EXC-1009"}]
    allowed, _ = available_actions(state, actor(Role.MANAGER))
    assert A.REOPEN not in allowed


def test_available_actions_for_staff_on_someone_elses_exception() -> None:
    allowed, blocked = available_actions(ExceptionState(S.OPEN, OTHER), actor(Role.STAFF))
    assert allowed == [A.ACKNOWLEDGE, A.ADD_NOTE]
    assert {(b.action, b.code) for b in blocked} == {
        (A.START, "ASSIGNED_TO_ANOTHER_USER"),
        (A.RESOLVE, "NOT_ASSIGNEE"),
        (A.DISMISS, "PERMISSION_DENIED"),
        (A.ASSIGN, "PERMISSION_DENIED"),
        (A.SET_DUE_DATE, "PERMISSION_DENIED"),
    }  # claim is not offered at all: only unassigned exceptions can be claimed


def test_available_actions_for_viewer_are_empty() -> None:
    allowed, blocked = available_actions(ExceptionState(S.OPEN, None), actor(Role.VIEWER))
    assert allowed == []
    assert all(b.code == "PERMISSION_DENIED" for b in blocked)


def test_available_actions_for_manager_on_resolved_exception() -> None:
    allowed, _ = available_actions(ExceptionState(S.RESOLVED, OTHER), actor(Role.MANAGER))
    assert allowed == [A.REOPEN, A.ADD_NOTE]


@pytest.mark.parametrize(
    ("note", "ok"),
    [
        ("Shipped it", False),  # 9 non-whitespace characters
        ("Shipped it!", True),  # 10
        ("          ", False),
        ("a b c d e f g h i j", True),
        ("  a b c d e f g h i  ", False),
    ],
)
def test_closing_notes_need_ten_non_whitespace_characters(note: str, ok: bool) -> None:
    """Resolution and dismissal notes: at least 10 non-whitespace characters (422)."""
    if ok:
        assert validate_closing_note(note, "resolution_note") == note.strip()
    else:
        with pytest.raises(BusinessRuleViolationError) as info:
            validate_closing_note(note, "resolution_note")
        assert (info.value.status_code, info.value.code) == (422, "VALIDATION_FAILED")


@pytest.mark.parametrize("code", [ResolutionCode.CONDITION_CLEARED, ResolutionCode.SUPERSEDED])
def test_system_resolution_codes_are_rejected_for_manual_resolution(code: ResolutionCode) -> None:
    with pytest.raises(BusinessRuleViolationError):
        validate_resolution_code(code)


def test_manual_resolution_code_schema_matches_the_model() -> None:
    assert {c.value for c in ManualResolutionCode} == {c.value for c in MANUAL_RESOLUTION_CODES}
