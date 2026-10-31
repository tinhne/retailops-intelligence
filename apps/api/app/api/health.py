"""Liveness and readiness probes used by Docker health checks and the hosting platform."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import error_body
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("app.health")


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
def ready(db: Session = Depends(get_db)) -> dict[str, str] | JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("readiness_db_unavailable", exc_info=True)
        return JSONResponse(
            status_code=503, content=error_body("DB_UNAVAILABLE", "Database is not reachable.")
        )
    return {"status": "ok", "database": "ok"}
