import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.audit import service
from app.domains.identity import service as identity
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext

router = APIRouter(prefix="/stores/{store_id}/audit-logs", tags=["audit"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None = Field(
        description="Full name of the actor (no email). Null for system actions."
    )
    store_id: uuid.UUID | None
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    request_id: str | None


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    action: str | None = Query(None, max_length=80, description="Action prefix, e.g. 'exception.'"),
    actor_user_id: uuid.UUID | None = None,
    occurred_from: datetime | None = Query(None, alias="from"),
    occurred_to: datetime | None = Query(None, alias="to"),
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.AUDIT_READ)),
    db: Session = Depends(get_db),
) -> Page[AuditLogOut]:
    rows, total = service.list_for_store(
        db,
        organization_id=ctx.organization_id,
        store_id=ctx.store_id,
        action_prefix=action,
        actor_user_id=actor_user_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        offset=paging.offset,
        limit=paging.page_size,
    )
    names = identity.user_names(db, (r.actor_user_id for r in rows if r.actor_user_id))
    return Page[AuditLogOut](
        items=[
            AuditLogOut(
                id=r.id,
                occurred_at=r.occurred_at,
                action=r.action,
                actor_user_id=r.actor_user_id,
                actor_name=names.get(r.actor_user_id) if r.actor_user_id else None,
                store_id=r.store_id,
                target_type=r.target_type,
                target_id=r.target_id,
                details=r.details,
                request_id=r.request_id,
            )
            for r in rows
        ],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )
