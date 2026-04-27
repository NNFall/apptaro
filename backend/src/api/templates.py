from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.settings import Settings, get_settings
from src.jobs.template_catalog import list_presentation_templates
from src.schemas.templates import PresentationTemplateItem, PresentationTemplatesResponse


router = APIRouter(prefix='/v1/templates', tags=['templates'])


@router.get('/presentation', response_model=PresentationTemplatesResponse)
async def get_presentation_templates(
    settings: Settings = Depends(get_settings),
) -> PresentationTemplatesResponse:
    items = list_presentation_templates(settings.templates_dir)
    return PresentationTemplatesResponse(
        templates=[PresentationTemplateItem(**item) for item in items]
    )
