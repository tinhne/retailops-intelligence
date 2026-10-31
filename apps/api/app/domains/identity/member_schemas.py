"""Schemas for organization member administration (ROLE_AND_PERMISSION_WORKFLOW.md §8)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domains.identity.permissions import Role
from app.domains.identity.schemas import Email

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class MemberStatus(StrEnum):
    """Account status of a member. v1 stores it on the user (``app_user.is_active``)."""

    ACTIVE = "ACTIVE"
    DEACTIVATED = "DEACTIVATED"


class OrganizationMemberOut(BaseModel):
    """A member as shown on the Users & roles screen (``users.read``)."""

    id: uuid.UUID = Field(description="Membership id, used in the member PATCH path.")
    user_id: uuid.UUID
    full_name: str
    email: str
    role: Role
    status: MemberStatus
    joined_at: datetime = Field(description="When the membership was created.")
    last_login_at: datetime | None


class OrganizationMemberList(BaseModel):
    items: list[OrganizationMemberOut]


class MemberCreate(BaseModel):
    """Add a member by creating their account (§8.1). The email must not have an account yet."""

    model_config = ConfigDict(extra="forbid")

    email: Email
    full_name: FullName
    role: Role


class MemberCreated(BaseModel):
    member: OrganizationMemberOut
    temporary_password: str = Field(
        description=(
            "Shown once so the owner can hand it over outside the product. Only its argon2id "
            "hash is stored; it is never logged or written to the audit log."
        )
    )


class MemberUpdate(BaseModel):
    """Change a member's role, deactivate or reactivate them (§8.2, §8.3).

    Omitted fields keep their value; an explicit ``null`` is rejected, and at least one field is
    required.
    """

    model_config = ConfigDict(extra="forbid")

    role: Role | None = None
    status: MemberStatus | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        if not self.model_fields_set:
            raise ValueError("Provide a role or a status to change.")
        return self
