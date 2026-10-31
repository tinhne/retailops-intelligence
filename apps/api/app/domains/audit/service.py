"""Audit recording and querying."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.context import current_client_ip, current_request_id
from app.domains.audit.models import AuditLog


def record(
    db: Session,
    *,
    action: str,
    organization_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    store_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit row to the current unit of work. The caller commits."""
    entry = AuditLog(
        organization_id=organization_id,
        store_id=store_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details or {},
        ip=current_client_ip(),
        request_id=current_request_id(),
    )
    db.add(entry)
    return entry


def list_for_store(
    db: Session,
    *,
    organization_id: uuid.UUID,
    store_id: uuid.UUID,
    action_prefix: str | None,
    actor_user_id: uuid.UUID | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    offset: int,
    limit: int,
) -> tuple[list[AuditLog], int]:
    """Entries for this store plus organization-level entries (store_id NULL) of its org."""
    stmt = select(AuditLog).where(
        AuditLog.organization_id == organization_id,
        or_(AuditLog.store_id == store_id, AuditLog.store_id.is_(None)),
    )
    if action_prefix:
        stmt = stmt.where(AuditLog.action.startswith(action_prefix, autoescape=True))
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if occurred_from:
        stmt = stmt.where(AuditLog.occurred_at >= occurred_from)
    if occurred_to:
        stmt = stmt.where(AuditLog.occurred_at < occurred_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total
