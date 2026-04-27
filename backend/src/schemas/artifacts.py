from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ArtifactItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    artifact_id: str
    kind: str
    filename: str
    media_type: str
    download_url: str
