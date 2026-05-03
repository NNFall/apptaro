from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from src.integrations.text_generation import PresentationGenerationClient
from src.domain.tarot_deck import card_line, draw_cards, load_deck


@dataclass(frozen=True)
class OutlineResult:
    title: str
    outline: list[str]
    slides_total: int
    content_slides: int


class PresentationOutlineService:
    def __init__(self, text_client: PresentationGenerationClient, cards_dir: Path | None = None) -> None:
        self._text_client = text_client
        self._cards_dir = cards_dir

    async def generate(self, topic: str, slides_total: int) -> OutlineResult:
        content_slides = 3
        title = await asyncio.to_thread(self._text_client.generate_title, topic)
        outline = self._draw_tarot_outline()
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
        content_slides = 3
        resolved_title = title or await asyncio.to_thread(self._text_client.generate_title, topic)
        updated_outline = self._draw_tarot_outline()
        return OutlineResult(
            title=resolved_title,
            outline=updated_outline,
            slides_total=slides_total,
            content_slides=content_slides,
        )

    def _draw_tarot_outline(self) -> list[str]:
        if self._cards_dir is None:
            return [
                'Текущая ситуация вокруг вопроса',
                'Ключевое препятствие или узел',
                'Совет и направление',
            ]
        deck = load_deck(self._cards_dir)
        cards = draw_cards(deck, count=3)
        positions = [
            'Текущая ситуация',
            'Ключевое препятствие',
            'Совет и направление',
        ]
        return [card_line(index, positions[index - 1], card) for index, card in enumerate(cards, start=1)]
