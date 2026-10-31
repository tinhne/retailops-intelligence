"""HTTP endpoints for the analytics module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}/analytics", tags=["analytics"])
