"""Roles and the role → permission matrix (ADR-0007).

The matrix is code, not data: it is reviewed, versioned and tested like any other business rule,
and cannot be widened by editing database rows.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    STAFF = "STAFF"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard.read"
    CATALOG_READ = "catalog.read"
    ORDERS_READ = "orders.read"
    INVENTORY_READ = "inventory.read"
    EXCEPTIONS_READ = "exceptions.read"
    EXCEPTIONS_WORK = "exceptions.work"
    EXCEPTIONS_ASSIGN = "exceptions.assign"
    EXCEPTIONS_MANAGE = "exceptions.manage"
    EVALUATIONS_RUN = "evaluations.run"
    IMPORTS_READ = "imports.read"
    IMPORTS_RUN = "imports.run"
    ANALYTICS_READ = "analytics.read"
    COPILOT_USE = "copilot.use"
    AUDIT_READ = "audit.read"
    SETTINGS_READ = "settings.read"
    SETTINGS_MANAGE = "settings.manage"
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"


_READ_ONLY = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.CATALOG_READ,
        Permission.ORDERS_READ,
        Permission.INVENTORY_READ,
        Permission.EXCEPTIONS_READ,
        Permission.IMPORTS_READ,
        Permission.ANALYTICS_READ,
        Permission.COPILOT_USE,
        Permission.SETTINGS_READ,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.MANAGER: frozenset(Permission) - {Permission.USERS_MANAGE},
    Role.STAFF: _READ_ONLY | {Permission.EXCEPTIONS_WORK},
    Role.ANALYST: _READ_ONLY | {Permission.AUDIT_READ},
    # Public demo visitors: read-only plus copilot. Never any mutating permission.
    Role.VIEWER: _READ_ONLY | {Permission.AUDIT_READ},
}

MUTATING_PERMISSIONS = frozenset(
    {
        Permission.EXCEPTIONS_WORK,
        Permission.EXCEPTIONS_ASSIGN,
        Permission.EXCEPTIONS_MANAGE,
        Permission.EVALUATIONS_RUN,
        Permission.IMPORTS_RUN,
        Permission.SETTINGS_MANAGE,
        Permission.USERS_MANAGE,
    }
)


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]
