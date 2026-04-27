from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.schemas.artifacts import ArtifactItem


class ConversionResultResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    conversion_id: str
    source_filename: str
    source_format: str
    target_format: str
    artifact: ArtifactItem
