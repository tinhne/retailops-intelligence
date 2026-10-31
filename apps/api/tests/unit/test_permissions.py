"""Role → permission matrix (ADR-0007, ROLE_AND_PERMISSION_WORKFLOW.md)."""

import pytest

from app.domains.identity.permissions import (
    MUTATING_PERMISSIONS,
    ROLE_PERMISSIONS,
    Permission,
    Role,
    permissions_for,
)


def test_every_role_has_a_permission_set() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_owner_has_every_permission() -> None:
    assert permissions_for(Role.OWNER) == frozenset(Permission)


def test_manager_cannot_manage_users_but_can_manage_operations() -> None:
    perms = permissions_for(Role.MANAGER)
    assert Permission.USERS_MANAGE not in perms
    assert {
        Permission.EXCEPTIONS_MANAGE,
        Permission.EXCEPTIONS_ASSIGN,
        Permission.IMPORTS_RUN,
        Permission.SETTINGS_MANAGE,
    } <= perms


def test_staff_can_work_exceptions_but_not_assign_dismiss_or_import() -> None:
    perms = permissions_for(Role.STAFF)
    assert Permission.EXCEPTIONS_WORK in perms
    assert Permission.EXCEPTIONS_ASSIGN not in perms
    assert Permission.EXCEPTIONS_MANAGE not in perms
    assert Permission.IMPORTS_RUN not in perms
    assert Permission.AUDIT_READ not in perms


@pytest.mark.parametrize("role", [Role.ANALYST, Role.VIEWER])
def test_read_only_roles_hold_no_mutating_permission(role: Role) -> None:
    assert permissions_for(role).isdisjoint(MUTATING_PERMISSIONS)
    assert Permission.COPILOT_USE in permissions_for(role)
