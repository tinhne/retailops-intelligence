"""Store details, operational settings (BUSINESS_RULES.md §7) and the member directory."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.audit import service as audit
from app.domains.identity.models import (
    DEFAULT_PRIORITY_WEIGHTS,
    Membership,
    StoreSettings,
    User,
)
from app.domains.identity.permissions import Permission, permissions_for
from app.domains.identity.service import StoreContext
from app.domains.identity.store_schemas import (
    MemberList,
    MemberOut,
    OrganizationOut,
    PriorityWeights,
    StoreOut,
    StoreSettingsOut,
    StoreSettingsUpdate,
)

CENT = Decimal("0.01")


def get_store(ctx: StoreContext) -> StoreOut:
    store = ctx.store
    org = store.organization
    return StoreOut(
        id=store.id,
        name=store.name,
        code=store.code,
        currency=store.currency,
        timezone=store.timezone,
        organization=OrganizationOut(id=org.id, name=org.name, is_demo=org.is_demo),
    )


def _settings_row(db: Session, store_id: uuid.UUID, *, for_update: bool = False) -> StoreSettings:
    """The store's settings row. A store without one gets the defaults of §7 (not committed)."""
    stmt = select(StoreSettings).where(StoreSettings.store_id == store_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if row is None:
        row = StoreSettings(store_id=store_id, priority_weights=dict(DEFAULT_PRIORITY_WEIGHTS))
        db.add(row)
        db.flush()
    return row


def _to_out(row: StoreSettings) -> StoreSettingsOut:
    return StoreSettingsOut(
        fulfillment_sla_hours=row.fulfillment_sla_hours,
        stall_threshold_hours=row.stall_threshold_hours,
        refund_overdue_hours=row.refund_overdue_hours,
        approaching_reorder_factor=row.approaching_reorder_factor,
        velocity_window_days=row.velocity_window_days,
        reopen_window_hours=row.reopen_window_hours,
        exposure_cap=row.exposure_cap,
        priority_weights=PriorityWeights.model_validate(row.priority_weights),
        evaluation_interval_minutes=row.evaluation_interval_minutes,
        updated_at=row.updated_at,
    )


def get_settings(db: Session, store_id: uuid.UUID) -> StoreSettingsOut:
    """Operational thresholds of one store. Other modules read settings through this function."""
    return _to_out(_settings_row(db, store_id))


def _audit_value(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


def update_settings(
    db: Session, ctx: StoreContext, changes: StoreSettingsUpdate
) -> StoreSettingsOut:
    """Apply a partial settings update and audit it as ``settings.update`` (BUSINESS_RULES.md §7).

    Only fields whose value actually changes are written and audited. A request that changes
    nothing writes no audit row. The row is locked so concurrent partial updates do not overwrite
    each other.
    """
    row = _settings_row(db, ctx.store_id, for_update=True)
    # JSON-compatible values; nulls were rejected by the schema. Decimals stay Decimal.
    requested: dict[str, Any] = changes.model_dump(exclude_unset=True)

    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for name, value in requested.items():
        if isinstance(value, Decimal):
            value = value.quantize(CENT)  # both Decimal settings are NUMERIC(_, 2)
        current = getattr(row, name)
        if current == value:
            continue
        before[name] = _audit_value(current)
        after[name] = _audit_value(value)
        setattr(row, name, value)

    if after:
        audit.record(
            db,
            action="settings.update",
            organization_id=ctx.organization_id,
            store_id=ctx.store_id,
            actor_user_id=ctx.user.id,
            target_type="store",
            target_id=ctx.store_id,
            details={"before": before, "after": after},
        )
    db.commit()
    db.refresh(row)
    return _to_out(row)


def list_members(db: Session, organization_id: uuid.UUID) -> MemberList:
    """Active members of the store's organization for the assignee picker (no emails)."""
    rows = db.execute(
        select(User.id, User.full_name, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == organization_id, User.is_active.is_(True))
        .order_by(User.full_name, User.id)
    ).all()
    return MemberList(
        items=[
            MemberOut(
                id=user_id,
                full_name=full_name,
                role=role.value,
                can_work_exceptions=Permission.EXCEPTIONS_WORK in permissions_for(role),
            )
            for user_id, full_name, role in rows
        ]
    )
