from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}


@dataclass(frozen=True)
class TarotCard:
    slug: str
    title: str
    image_path: Path


@dataclass(frozen=True)
class DrawnCard:
    card: TarotCard
    is_reversed: bool


def humanize_card_name(slug: str) -> str:
    name = slug.replace('_', ' ').replace('-', ' ').strip()
    if not name:
        return slug
    return ' '.join(part.capitalize() for part in name.split())


def slugify_card_title(title: str) -> str:
    value = title.strip().lower()
    value = value.replace('(перевернутая)', '').replace('(перевернутая)', '')
    value = value.replace('(прямая)', '').replace('(прямая)', '')
    value = value.replace('ё', 'е')
    parts = [part for part in value.replace('-', ' ').split() if part]
    return '_'.join(parts)


def load_deck(cards_dir: str | Path) -> list[TarotCard]:
    root = Path(cards_dir)
    if not root.exists():
        return []

    cards: list[TarotCard] = []
    for file in sorted(root.rglob('*')):
        if not file.is_file() or file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        cards.append(
            TarotCard(
                slug=file.stem,
                title=humanize_card_name(file.stem),
                image_path=file,
            )
        )
    return cards


def draw_cards(deck: list[TarotCard], count: int = 3) -> list[DrawnCard]:
    if len(deck) < count:
        raise ValueError(f'Not enough tarot cards in deck: required={count}, available={len(deck)}')
    selected = random.sample(deck, count)
    return [DrawnCard(card=card, is_reversed=bool(random.getrandbits(1))) for card in selected]


def restore_drawn_cards(cards_dir: str | Path, items: list[dict]) -> list[DrawnCard]:
    index = {card.slug: card for card in load_deck(cards_dir)}
    restored: list[DrawnCard] = []
    for item in items:
        slug = str(item.get('slug', '')).strip()
        card = index.get(slug)
        if card is None:
            continue
        restored.append(DrawnCard(card=card, is_reversed=bool(item.get('rev'))))
    return restored


def card_line(index: int, position: str, drawn: DrawnCard) -> str:
    orientation = 'перевернутая' if drawn.is_reversed else 'прямая'
    return f'{position} — {drawn.card.title} ({orientation}) [card={drawn.card.slug};rev={int(drawn.is_reversed)}]'


def parse_card_lines(cards_dir: str | Path, lines: list[str]) -> list[DrawnCard]:
    deck = load_deck(cards_dir)
    index = {card.slug: card for card in deck}
    result: list[DrawnCard] = []
    for line in lines:
        marker = ''
        if '[card=' in line and ']' in line:
            marker = line.split('[card=', 1)[1].split(']', 1)[0]
        slug = ''
        rev = False
        if marker:
            for part in marker.split(';'):
                if part.startswith('rev='):
                    rev = part.split('=', 1)[1].strip() in {'1', 'true', 'True'}
                elif part.strip():
                    slug = part.strip()
        if not slug:
            title_part = line.split('—', 1)[-1].strip() if '—' in line else line
            slug = slugify_card_title(title_part)
        card = index.get(slug)
        if card:
            result.append(DrawnCard(card=card, is_reversed=rev))
    return result


def display_card_line(line: str) -> str:
    return line.split(' [card=', 1)[0].strip()
