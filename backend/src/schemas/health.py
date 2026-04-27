from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: str
    service: str
    environment: str
    version: str
