from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.domain.tarot_deck import DrawnCard, TarotCard  # noqa: E402
from src.domain.presentation_render_service import _cards_block  # noqa: E402
from src.integrations.text_generation import PresentationGenerationClient  # noqa: E402


CYRILLIC_RE = r'[\u0400-\u04FF]'
MOJIBAKE_MARKERS = (
    '\u0420',
    '\u0421',
    '\u0432\u0402',
    '\u0440\u045f',
)


class GenerationFallbackLocalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = PresentationGenerationClient(
            api_key='',
            base_url='',
            text_model='',
            image_model='',
        )

    def test_slide_content_fallback_defaults_to_english(self) -> None:
        slides = self.client.generate_slide_contents(
            'Will my project launch well?',
            ['Current situation', 'Key obstacle'],
            language='en',
        )
        text = '\n'.join(f'{item["title"]}\n{item["text"]}\n{item["image_prompt"]}' for item in slides)

        self.assertIn('Short text for the question', text)
        self._assert_clean_english(text)

    def test_tarot_reading_fallback_defaults_to_english(self) -> None:
        text = self.client.generate_tarot_reading(
            'Will my project launch well?',
            '1. Current situation around the question - The Tower (upright)',
            mode='teaser',
            language='en',
        )

        self.assertIn('Let us see what the cards are saying', text)
        self.assertIn('Unlock the full reading', text)
        self._assert_clean_english(text)

    def test_tarot_continuation_fallback_defaults_to_english(self) -> None:
        text = self.client.generate_tarot_continuation(
            'Will my project launch well?',
            'The Tower (upright)',
            'The first card shows pressure around the launch.',
            '2. Key obstacle or tension - The Moon (reversed)\n'
            '3. Advice and direction - Strength (upright)',
            language='en',
        )

        self.assertIn('Connection with the first card', text)
        self.assertIn('*Summary:*', text)
        self._assert_clean_english(text)

    def test_render_cards_block_defaults_to_english(self) -> None:
        card = TarotCard(slug='tower', title='Fallback Russian Title', image_path=Path('tower.jpg'))
        drawn = DrawnCard(card=card, is_reversed=True)

        text = _cards_block([drawn], language='en')

        self.assertEqual(text, '1. Current situation around the question - Tower (reversed)')
        self._assert_clean_english(text)

    def _assert_clean_english(self, text: str) -> None:
        self.assertNotRegex(text, CYRILLIC_RE)
        for marker in MOJIBAKE_MARKERS:
            self.assertNotIn(marker, text)


if __name__ == '__main__':
    unittest.main()
