from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

ENGLISH_CARD_TITLES = {
    'башня': 'The Tower',
    'верховная_жрица': 'The High Priestess',
    'влюбленные': 'The Lovers',
    'восьмерка_жезлов': 'Eight of Wands',
    'восьмерка_мечей': 'Eight of Swords',
    'восьмерка_пентаклей': 'Eight of Pentacles',
    'восьмерка_чаш': 'Eight of Cups',
    'двойка_жезлов': 'Two of Wands',
    'двойка_мечей': 'Two of Swords',
    'двойка_пентаклей': 'Two of Pentacles',
    'двойка_чаш': 'Two of Cups',
    'девятка_жезлов': 'Nine of Wands',
    'девятка_мечей': 'Nine of Swords',
    'девятка_пентаклей': 'Nine of Pentacles',
    'девятка_чаш': 'Nine of Cups',
    'десятка_жезлов': 'Ten of Wands',
    'десятка_мечей': 'Ten of Swords',
    'десятка_пентаклей': 'Ten of Pentacles',
    'десятка_чаш': 'Ten of Cups',
    'дурак': 'The Fool',
    'дьявол': 'The Devil',
    'звезда': 'The Star',
    'иерофант': 'The Hierophant',
    'император': 'The Emperor',
    'императрица': 'The Empress',
    'колесница': 'The Chariot',
    'колесо_фортуны': 'Wheel of Fortune',
    'королева_жезлов': 'Queen of Wands',
    'королева_мечей': 'Queen of Swords',
    'королева_пентаклей': 'Queen of Pentacles',
    'королева_чаш': 'Queen of Cups',
    'король_жезлов': 'King of Wands',
    'король_мечей': 'King of Swords',
    'король_пентаклей': 'King of Pentacles',
    'король_чаш': 'King of Cups',
    'луна': 'The Moon',
    'маг': 'The Magician',
    'мир': 'The World',
    'отшельник': 'The Hermit',
    'паж_жезлов': 'Page of Wands',
    'паж_мечей': 'Page of Swords',
    'паж_пентаклей': 'Page of Pentacles',
    'паж_чаш': 'Page of Cups',
    'повешенный': 'The Hanged Man',
    'пятерка_жезлов': 'Five of Wands',
    'пятерка_мечей': 'Five of Swords',
    'пятерка_пентаклей': 'Five of Pentacles',
    'пятерка_чаш': 'Five of Cups',
    'рыцарь_жезлов': 'Knight of Wands',
    'рыцарь_мечей': 'Knight of Swords',
    'рыцарь_пентаклей': 'Knight of Pentacles',
    'рыцарь_чаш': 'Knight of Cups',
    'семерка_жезлов': 'Seven of Wands',
    'семерка_мечей': 'Seven of Swords',
    'семерка_пентаклей': 'Seven of Pentacles',
    'семерка_чаш': 'Seven of Cups',
    'сила': 'Strength',
    'смерть': 'Death',
    'солнце': 'The Sun',
    'справедливость': 'Justice',
    'суд': 'Judgement',
    'тройка_жезлов': 'Three of Wands',
    'тройка_мечей': 'Three of Swords',
    'тройка_пентаклей': 'Three of Pentacles',
    'тройка_чаш': 'Three of Cups',
    'туз_жезлов': 'Ace of Wands',
    'туз_мечей': 'Ace of Swords',
    'туз_пентаклей': 'Ace of Pentacles',
    'туз_чаш': 'Ace of Cups',
    'умеренность': 'Temperance',
    'четверка_жезлов': 'Four of Wands',
    'четверка_мечей': 'Four of Swords',
    'четверка_пентаклей': 'Four of Pentacles',
    'четверка_чаш': 'Four of Cups',
    'шестерка_жезлов': 'Six of Wands',
    'шестерка_мечей': 'Six of Swords',
    'шестерка_пентаклей': 'Six of Pentacles',
    'шестерка_чаш': 'Six of Cups',
}
ENGLISH_TITLE_TO_SLUG = {
    title.lower(): slug for slug, title in ENGLISH_CARD_TITLES.items()
}


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
    value = value.replace('(reversed)', '').replace('(upright)', '')
    value = value.replace('ё', 'е')
    value = value.strip(' -—')
    english_slug = ENGLISH_TITLE_TO_SLUG.get(value)
    if english_slug:
        return english_slug
    parts = [part for part in value.replace('-', ' ').split() if part]
    return '_'.join(parts)


def localized_card_title(card: TarotCard, language: str = 'ru') -> str:
    if language == 'en':
        return ENGLISH_CARD_TITLES.get(card.slug, humanize_card_name(card.slug))
    return card.title


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


def card_line(index: int, position: str, drawn: DrawnCard, language: str = 'ru') -> str:
    if language == 'en':
        orientation = 'reversed' if drawn.is_reversed else 'upright'
        title = localized_card_title(drawn.card, language=language)
        return f'{position} - {title} ({orientation}) [card={drawn.card.slug};rev={int(drawn.is_reversed)}]'
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
