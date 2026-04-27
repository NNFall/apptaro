from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PresentationTemplateItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    template_path: str | None
    preview_path: str | None
    template_available: bool
    preview_available: bool


class PresentationTemplatesResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    templates: list[PresentationTemplateItem]
