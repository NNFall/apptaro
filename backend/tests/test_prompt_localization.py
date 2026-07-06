from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.domain.presentation_prompts import tarot_continuation_prompt, tarot_reading_prompt  # noqa: E402


class PromptLocalizationTests(unittest.TestCase):
    def test_tarot_reading_prompt_uses_english_language_instruction(self) -> None:
        prompt = tarot_reading_prompt(
            'Will my project launch well?',
            '1. Current situation around the question - The Magician (upright)',
            mode='teaser',
            language='en',
        )

        self.assertIn('Answer only in English', prompt)
        self.assertIn('SYSTEM INSTRUCTIONS:', prompt)
        self.assertIn('USER REQUEST:', prompt)
        self.assertIn('Will my project launch well?', prompt)
        self.assertIn('Do not mention cards 2 or 3', prompt)

    def test_tarot_continuation_prompt_uses_english_language_instruction(self) -> None:
        prompt = tarot_continuation_prompt(
            question='What should I focus on next?',
            first_card_line='The Star (upright)',
            first_text='The first card points to hope.',
            cards_block='2. Key obstacle or knot - The Tower (reversed)\n3. Advice and direction - Strength (upright)',
            language='en',
        )

        self.assertIn('Answer only in English', prompt)
        self.assertIn('This is a continuation', prompt)
        self.assertIn('What should I focus on next?', prompt)
        self.assertIn('*Summary:*', prompt)

    def test_russian_prompt_does_not_use_english_instruction(self) -> None:
        prompt = tarot_reading_prompt(
            'Love',
            '1. Card - Magician (upright)',
            mode='teaser',
            language='ru',
        )

        self.assertNotIn('Answer only in English', prompt)
        self.assertIn('Love', prompt)


if __name__ == '__main__':
    unittest.main()
