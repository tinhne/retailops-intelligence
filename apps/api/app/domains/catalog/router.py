"""HTTP endpoints for the catalog module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}", tags=["catalog"])
