from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.domain.tarot_deck import (  # noqa: E402
    DrawnCard,
    TarotCard,
    card_line,
    localized_card_title,
    slugify_card_title,
)


class TarotDeckLocalizationTests(unittest.TestCase):
    def test_english_card_line_uses_english_title_and_orientation(self) -> None:
        card = TarotCard(
            slug='башня',
            title='Башня',
            image_path=Path('tower.jpg'),
        )
        drawn = DrawnCard(card=card, is_reversed=False)

        self.assertEqual(localized_card_title(card, language='en'), 'The Tower')
        self.assertEqual(
            card_line(1, 'Current situation', drawn, language='en'),
            'Current situation - The Tower (upright) [card=башня;rev=0]',
        )

    def test_english_card_title_can_be_restored_to_russian_slug(self) -> None:
        self.assertEqual(slugify_card_title('The Tower (upright)'), 'башня')
        self.assertEqual(slugify_card_title('Seven of Cups (reversed)'), 'семерка_чаш')


if __name__ == '__main__':
    unittest.main()
