"""HTTP endpoints for the orders module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}/orders", tags=["orders"])
