"""Store details and operational settings endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/stores/{store_id}", tags=["stores"])
