from __future__ import annotations

from fastapi import APIRouter

from src.api.billing import router as billing_router
from src.api.artifacts import router as artifacts_router
from src.api.conversions import router as conversions_router
from src.api.health import router as health_router
from src.api.presentations import router as presentations_router
from src.api.templates import router as templates_router


api_router = APIRouter()
api_router.include_router(artifacts_router)
api_router.include_router(billing_router)
api_router.include_router(conversions_router)
api_router.include_router(health_router)
api_router.include_router(presentations_router)
api_router.include_router(templates_router)
