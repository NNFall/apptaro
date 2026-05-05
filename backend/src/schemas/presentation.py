from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from src.schemas.artifacts import ArtifactItem


TopicStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
CommentStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
OutlineItemStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class OutlineGenerateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    topic: TopicStr
    slides_total: Annotated[int, Field(ge=4, le=10)]


class OutlineReviseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    topic: TopicStr
    slides_total: Annotated[int, Field(ge=4, le=10)]
    outline: list[OutlineItemStr]
    comment: CommentStr
    title: str | None = None

    @field_validator('outline')
    @classmethod
    def validate_outline(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError('Outline must contain at least one item')
        return value


class OutlineResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    title: str
    outline: list[str]
    slides_total: int
    content_slides: int
    teaser_mode: bool = False
    teaser_text: str | None = None
    teaser_artifacts: list[ArtifactItem] = Field(default_factory=list)


class PresentationRenderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    topic: TopicStr
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    outline: list[OutlineItemStr]
    design_id: Annotated[int, Field(ge=1, le=4)]
    generate_pdf: bool = True
    teaser_first_text: str | None = None

    @field_validator('outline')
    @classmethod
    def validate_render_outline(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError('Outline must contain at least one item')
        return value


class PresentationRenderResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    presentation_id: str
    title: str
    design_id: int
    slides_total: int
    content_slides: int
    artifacts: list[ArtifactItem]
