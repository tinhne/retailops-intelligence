"""Aggregates all v1 routers."""

from fastapi import APIRouter

from app.api import health
from app.domains.audit.router import router as audit_router
from app.domains.identity.router import router as auth_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(audit_router)
