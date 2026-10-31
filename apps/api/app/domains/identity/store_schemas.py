"""Schemas for store details, operational settings (BUSINESS_RULES.md §7) and store members."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.analytics.schemas import DataFreshness
from app.domains.identity.permissions import Role

# Integers in settings are strict: JSON booleans, floats and numeric strings are rejected.
Weight = Annotated[int, Field(strict=True, ge=0, le=100)]
Hours = Annotated[int, Field(strict=True, ge=1, le=8760)]

MAX_PRIORITY_SCORE = 100


class SeverityWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    CRITICAL: Weight
    HIGH: Weight
    MEDIUM: Weight
    LOW: Weight


class DeadlineWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overdue: Weight
    within_24h: Weight
    within_72h: Weight


class PriorityWeights(BaseModel):
    """Same shape as ``DEFAULT_PRIORITY_WEIGHTS`` (PRIORITY_MODEL.md, Configuration).

    Every component is a non-negative integer, and the highest score the weights can produce
    (``max S + cap_A + cap_E + max D + cap_T``) must not exceed 100.
    """

    model_config = ConfigDict(extra="forbid")

    severity: SeverityWeights
    affected_orders_per_order: Weight
    affected_orders_cap: Weight
    exposure_cap_points: Weight
    deadline: DeadlineWeights
    age_points_per_day: Weight
    age_cap: Weight

    @property
    def max_possible_score(self) -> int:
        s = self.severity
        d = self.deadline
        return (
            max(s.CRITICAL, s.HIGH, s.MEDIUM, s.LOW)
            + self.affected_orders_cap
            + self.exposure_cap_points
            + max(d.overdue, d.within_24h, d.within_72h)
            + self.age_cap
        )

    @model_validator(mode="after")
    def _max_total(self) -> Self:
        if self.max_possible_score > MAX_PRIORITY_SCORE:
            raise ValueError(
                f"The weights allow a score of {self.max_possible_score}; "
                f"the maximum possible total must be at most {MAX_PRIORITY_SCORE}"
            )
        return self


class StoreSettingsOut(BaseModel):
    fulfillment_sla_hours: int = Field(description="BR-201: ship_by = paid_at + this many hours.")
    stall_threshold_hours: int = Field(description="BR-203")
    refund_overdue_hours: int = Field(description="BR-206")
    approaching_reorder_factor: Decimal = Field(description="§2.5 APPROACHING_REORDER_POINT")
    velocity_window_days: int = Field(description="BR-150")
    reopen_window_hours: int = Field(description="STATE_MACHINES.md §3.3")
    exposure_cap: Decimal = Field(description="PRIORITY_MODEL.md exposure component")
    priority_weights: PriorityWeights
    evaluation_interval_minutes: int
    updated_at: datetime | None


class StoreSettingsUpdate(BaseModel):
    """Partial update. Omitted fields keep their value; an explicit ``null`` is rejected."""

    model_config = ConfigDict(extra="forbid")

    fulfillment_sla_hours: Hours | None = None
    stall_threshold_hours: Hours | None = None
    refund_overdue_hours: Hours | None = None
    approaching_reorder_factor: (
        Annotated[
            Decimal,
            Field(ge=Decimal("1.00"), le=Decimal("3.00"), max_digits=3, decimal_places=2),
        ]
        | None
    ) = None
    velocity_window_days: Annotated[int, Field(strict=True, ge=7, le=90)] | None = None
    reopen_window_hours: Hours | None = None
    exposure_cap: (
        Annotated[
            Decimal,
            Field(gt=Decimal("0"), le=Decimal("9999999999.99"), decimal_places=2),
        ]
        | None
    ) = None
    priority_weights: PriorityWeights | None = None
    evaluation_interval_minutes: Annotated[int, Field(strict=True, ge=5, le=1440)] | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> Self:
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"These settings cannot be null: {', '.join(nulls)}")
        return self


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    is_demo: bool


class StoreOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    currency: str
    timezone: str
    organization: OrganizationOut


class StoreDetailOut(BaseModel):
    store: StoreOut
    settings: StoreSettingsOut
    data_freshness: DataFreshness


class MemberOut(BaseModel):
    """A member as shown in the assignee picker. Emails are deliberately not exposed."""

    id: uuid.UUID
    full_name: str
    role: Role
    can_work_exceptions: bool


class MemberList(BaseModel):
    items: list[MemberOut]
