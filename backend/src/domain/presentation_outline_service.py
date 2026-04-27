from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.integrations.text_generation import PresentationGenerationClient


@dataclass(frozen=True)
class OutlineResult:
    title: str
    outline: list[str]
    slides_total: int
    content_slides: int


class PresentationOutlineService:
    def __init__(self, text_client: PresentationGenerationClient) -> None:
        self._text_client = text_client

    async def generate(self, topic: str, slides_total: int) -> OutlineResult:
        content_slides = max(1, slides_total - 1)
        title, outline = await asyncio.gather(
            asyncio.to_thread(self._text_client.generate_title, topic),
            asyncio.to_thread(self._text_client.generate_outline, topic, content_slides),
        )
        return OutlineResult(
            title=title,
            outline=outline,
            slides_total=slides_total,
            content_slides=content_slides,
        )

    async def revise(
        self,
        topic: str,
        slides_total: int,
        outline: list[str],
        comment: str,
        title: str | None = None,
    ) -> OutlineResult:
        content_slides = max(1, slides_total - 1)
        resolved_title = title or await asyncio.to_thread(self._text_client.generate_title, topic)
        updated_outline = await asyncio.to_thread(
            self._text_client.revise_outline,
            topic,
            content_slides,
            outline,
            comment,
        )
        return OutlineResult(
            title=resolved_title,
            outline=updated_outline,
            slides_total=slides_total,
            content_slides=content_slides,
        )
