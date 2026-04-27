from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.settings import Settings, get_settings
from src.schemas.health import HealthResponse


router = APIRouter(tags=['system'])


@router.get('/v1/health', response_model=HealthResponse)
async def healthcheck(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status='ok',
        service=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )
