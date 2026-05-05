from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image

from src.integrations.text_generation import PresentationGenerationClient
from src.domain.tarot_deck import DrawnCard, display_card_line, draw_cards, load_deck, parse_card_lines
from src.domain.tarot_layout import compose_spread_image
from src.repositories.artifacts import StoredArtifact, register_artifact


@dataclass(frozen=True)
class RenderedPresentation:
    presentation_id: str
    title: str
    design_id: int
    slides_total: int
    content_slides: int
    artifacts: list[StoredArtifact]
    reading_text: str = ''


@dataclass(frozen=True)
class TeaserPreview:
    text: str
    image_artifact: StoredArtifact


class PresentationRenderService:
    def __init__(
        self,
        generation_client: PresentationGenerationClient,
        temp_dir: Path,
        templates_dir: Path,
        tarot_cards_dir: Path,
        tarot_background_path: Path,
        tarot_layout_path: Path,
        libreoffice_path: str,
        image_concurrency: int = 5,
    ) -> None:
        self._generation_client = generation_client
        self._temp_dir = temp_dir
        self._templates_dir = templates_dir
        self._tarot_cards_dir = tarot_cards_dir
        self._tarot_background_path = tarot_background_path
        self._tarot_layout_path = tarot_layout_path
        self._libreoffice_path = libreoffice_path
        self._image_concurrency = max(1, image_concurrency)

    async def render(
        self,
        topic: str,
        title: str,
        outline: list[str],
        design_id: int,
        generate_pdf: bool = True,
    ) -> RenderedPresentation:
        presentation_id = uuid4().hex
        job_dir = self._temp_dir / 'tarot' / presentation_id
        job_dir.mkdir(parents=True, exist_ok=True)

        cards = parse_card_lines(self._tarot_cards_dir, outline)
        if len(cards) < 3:
            deck = load_deck(self._tarot_cards_dir)
            cards = draw_cards(deck, count=3)

        cards_block = _cards_block(cards)
        reading_text = await asyncio.to_thread(
            self._generation_client.generate_tarot_reading,
            topic,
            cards_block,
            mode='full',
        )

        base_name = _safe_filename(title) or 'tarot-reading'
        image_path = job_dir / f'{base_name}.jpg'
        text_path = job_dir / f'{base_name}.txt'

        await asyncio.to_thread(
            compose_spread_image,
            cards,
            image_path,
            self._tarot_layout_path,
            self._tarot_background_path,
        )
        text_path.write_text(
            f'{title}\n\nВопрос: {topic}\n\n{_visible_outline(outline)}\n\n{reading_text}\n',
            encoding='utf-8',
        )

        artifacts: list[StoredArtifact] = [
            register_artifact(
                image_path,
                kind='image',
                media_type='image/jpeg',
            ),
            register_artifact(
                text_path,
                kind='txt',
                media_type='text/plain; charset=utf-8',
            ),
        ]

        return RenderedPresentation(
            presentation_id=presentation_id,
            title=title,
            design_id=design_id,
            slides_total=3,
            content_slides=3,
            artifacts=artifacts,
            reading_text=reading_text,
        )

    async def render_teaser(
        self,
        topic: str,
        title: str,
        outline: list[str],
    ) -> TeaserPreview:
        cards = parse_card_lines(self._tarot_cards_dir, outline)
        if not cards:
            deck = load_deck(self._tarot_cards_dir)
            cards = draw_cards(deck, count=1)
        first_card = cards[0]
        cards_block = _cards_block([first_card])
        teaser_text = await asyncio.to_thread(
            self._generation_client.generate_tarot_reading,
            topic,
            cards_block,
            mode='teaser',
        )

        teaser_dir = self._temp_dir / 'tarot' / 'teaser'
        teaser_dir.mkdir(parents=True, exist_ok=True)
        base_name = _safe_filename(title) or 'tarot-teaser'
        image_path = teaser_dir / f'{base_name}-{uuid4().hex}.jpg'
        await asyncio.to_thread(_render_single_card_image, first_card, image_path)

        image_artifact = register_artifact(
            image_path,
            kind='image',
            media_type='image/jpeg',
        )
        return TeaserPreview(
            text=teaser_text,
            image_artifact=image_artifact,
        )


def _safe_filename(value: str) -> str:
    base = value.strip()
    base = re.sub(r'[^A-Za-zА-Яа-я0-9 _-]+', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    if not base:
        return 'presentation'
    if len(base) > 60:
        base = base[:57].rstrip() + '...'
    return base


def _cards_block(cards: list[DrawnCard]) -> str:
    positions = [
        'Текущая ситуация вокруг вопроса',
        'Ключевое препятствие или узел',
        'Совет и направление',
    ]
    lines = []
    for index, drawn in enumerate(cards[:3]):
        orientation = 'перевернутая' if drawn.is_reversed else 'прямая'
        lines.append(f'{index + 1}. {positions[index]} — {drawn.card.title} ({orientation})')
    return '\n'.join(lines)


def _visible_outline(outline: list[str]) -> str:
    return '\n'.join(f'{index}. {display_card_line(line)}' for index, line in enumerate(outline, start=1))


def _render_single_card_image(card: DrawnCard, output_path: Path) -> None:
    image = Image.open(card.card.image_path).convert('RGBA')
    if card.is_reversed:
        image = image.rotate(180, expand=True, resample=Image.Resampling.BICUBIC)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(output_path, format='JPEG', quality=95)
