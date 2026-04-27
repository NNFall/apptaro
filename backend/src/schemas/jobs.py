from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    job_id: str
    job_type: str
    status: str
    created_at: str
    updated_at: str
    error: str | None
    result: dict[str, Any] | None
