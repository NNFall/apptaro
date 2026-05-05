from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image

from src.domain.tarot_deck import DrawnCard, card_line, display_card_line, draw_cards, load_deck, parse_card_lines
from src.domain.tarot_layout import compose_spread_image
from src.integrations.text_generation import PresentationGenerationClient
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
        teaser_first_text: str | None = None,
    ) -> RenderedPresentation:
        _ = generate_pdf
        presentation_id = uuid4().hex
        job_dir = self._temp_dir / 'tarot' / presentation_id
        job_dir.mkdir(parents=True, exist_ok=True)

        parsed_cards = parse_card_lines(self._tarot_cards_dir, outline)
        continuation_mode = len(parsed_cards) == 1 and bool((teaser_first_text or '').strip())
        if continuation_mode:
            return await self._render_continuation(
                topic=topic,
                title=title,
                design_id=design_id,
                outline=outline,
                first_card=parsed_cards[0],
                first_text=(teaser_first_text or '').strip(),
                presentation_id=presentation_id,
                job_dir=job_dir,
            )

        cards = parsed_cards
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
            cards = [DrawnCard(card=cards[0].card, is_reversed=False)]
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

    async def _render_continuation(
        self,
        *,
        topic: str,
        title: str,
        design_id: int,
        outline: list[str],
        first_card: DrawnCard,
        first_text: str,
        presentation_id: str,
        job_dir: Path,
    ) -> RenderedPresentation:
        deck = load_deck(self._tarot_cards_dir)
        remaining_deck = [item for item in deck if item.slug != first_card.card.slug]
        if len(remaining_deck) < 2:
            raise ValueError('Not enough tarot cards to render continuation flow')
        continuation_cards = draw_cards(remaining_deck, count=2)

        continuation_block = _cards_block(continuation_cards, start_position=2)
        first_card_line = display_card_line(outline[0]) if outline else _single_card_display_line(first_card)
        reading_text = await asyncio.to_thread(
            self._generation_client.generate_tarot_continuation,
            topic,
            first_card_line,
            first_text,
            continuation_block,
        )

        base_name = _safe_filename(title) or 'tarot-reading'
        image_path = job_dir / f'{base_name}.jpg'
        text_path = job_dir / f'{base_name}.txt'

        await asyncio.to_thread(
            _render_two_cards_image,
            continuation_cards,
            image_path,
            self._tarot_background_path,
        )
        continuation_outline = [
            outline[0] if outline else card_line(1, 'Первая карта', first_card),
            card_line(2, 'Ключевое препятствие', continuation_cards[0]),
            card_line(3, 'Совет и направление', continuation_cards[1]),
        ]
        text_path.write_text(
            f'{title}\n\nВопрос: {topic}\n\n{_visible_outline(continuation_outline)}\n\n{reading_text}\n',
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


def _safe_filename(value: str) -> str:
    base = value.strip()
    base = re.sub(r'[^A-Za-zА-Яа-я0-9 _-]+', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    if not base:
        return 'presentation'
    if len(base) > 60:
        base = base[:57].rstrip() + '...'
    return base


def _position_label(position: int) -> str:
    mapping = {
        1: 'Текущая ситуация вокруг вопроса',
        2: 'Ключевое препятствие или узел',
        3: 'Совет и направление',
    }
    return mapping.get(position, f'Позиция {position}')


def _cards_block(cards: list[DrawnCard], *, start_position: int = 1) -> str:
    lines = []
    for offset, drawn in enumerate(cards):
        position = start_position + offset
        orientation = 'перевернутая' if drawn.is_reversed else 'прямая'
        lines.append(f'{position}. {_position_label(position)} — {drawn.card.title} ({orientation})')
    return '\n'.join(lines)


def _visible_outline(outline: list[str]) -> str:
    return '\n'.join(f'{index}. {display_card_line(line)}' for index, line in enumerate(outline, start=1))


def _single_card_display_line(card: DrawnCard) -> str:
    orientation = 'перевернутая' if card.is_reversed else 'прямая'
    return f'{card.card.title} ({orientation})'


def _render_single_card_image(card: DrawnCard, output_path: Path) -> None:
    image = Image.open(card.card.image_path).convert('RGBA')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(output_path, format='JPEG', quality=95)


def _render_two_cards_image(cards: list[DrawnCard], output_path: Path, background_path: Path) -> None:
    if len(cards) < 2:
        raise ValueError('Two drawn cards required')

    canvas_width = 1280
    canvas_height = 720
    if background_path.exists():
        background = Image.open(background_path).convert('RGBA')
        background = background.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
    else:
        background = Image.new('RGBA', (canvas_width, canvas_height), (40, 42, 58, 255))

    card_width = 420
    card_height = 620
    gap = 44
    start_x = (canvas_width - (card_width * 2 + gap)) // 2
    y = (canvas_height - card_height) // 2

    for index, drawn in enumerate(cards[:2]):
        image = Image.open(drawn.card.image_path).convert('RGBA')
        image = image.resize((card_width, card_height), Image.Resampling.LANCZOS)
        if drawn.is_reversed:
            image = image.rotate(180, expand=True, resample=Image.Resampling.BICUBIC)
        x = start_x + (card_width + gap) * index + (card_width - image.width) // 2
        paste_y = y + (card_height - image.height) // 2
        background.alpha_composite(image, (x, paste_y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.convert('RGB').save(output_path, format='JPEG', quality=95)
