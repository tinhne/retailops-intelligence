"""HTTP endpoints for the imports module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}/imports", tags=["imports"])
