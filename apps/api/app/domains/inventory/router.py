"""HTTP endpoints for the inventory module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}/inventory", tags=["inventory"])
