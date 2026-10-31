"""HTTP endpoints for the exceptions module. See docs/architecture/API_CONVENTIONS.md."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}", tags=["exceptions"])
