import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.domains.identity.permissions import Permission, Role

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$"
    ),
]


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)


class StoreSummary(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    currency: str
    timezone: str


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    is_demo: bool
    role: Role
    permissions: list[Permission]
    stores: list[StoreSummary]


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str


class RolePermissionsOut(BaseModel):
    role: Role
    permissions: list[Permission]


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
    csrf_token: str


class AuthOptionsOut(BaseModel):
    """What this installation's sign-in page may offer."""

    demo_available: bool


class CsrfTokenOut(BaseModel):
    """The value to send as ``X-CSRF-Token``; the same value is set in the ``ro_csrf`` cookie."""

    csrf_token: str
