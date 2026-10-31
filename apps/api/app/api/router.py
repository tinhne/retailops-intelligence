"""Aggregates all v1 routers."""

from fastapi import APIRouter

from app.api import health
from app.domains.analytics.router import router as analytics_router
from app.domains.audit.router import router as audit_router
from app.domains.catalog.router import router as catalog_router
from app.domains.exceptions.router import router as exceptions_router
from app.domains.identity.router import roles_router
from app.domains.identity.router import router as auth_router
from app.domains.identity.store_router import router as store_router
from app.domains.imports.router import router as imports_router
from app.domains.inventory.router import router as inventory_router
from app.domains.orders.router import router as orders_router

api_router = APIRouter(prefix="/api/v1")
for module_router in (
    health.router,
    auth_router,
    roles_router,
    store_router,
    catalog_router,
    orders_router,
    inventory_router,
    imports_router,
    exceptions_router,
    analytics_router,
    audit_router,
):
    api_router.include_router(module_router)
