from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.domain.presentation_prompts import (  # noqa: E402
    tarot_continuation_prompt,
    tarot_followup_prompt,
    tarot_reading_prompt,
)


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
        self.assertIn('Отвечай только на русском языке', prompt)
        self.assertIn('СИСТЕМНЫЕ ИНСТРУКЦИИ:', prompt)
        self.assertIn('ЗАПРОС ПОЛЬЗОВАТЕЛЯ:', prompt)
        self.assertIn('Love', prompt)

    def test_english_prompts_do_not_leak_russian_system_copy(self) -> None:
        reading = tarot_reading_prompt(
            'What should I do next?',
            '1. Current situation around the question - The Magician (upright)',
            mode='teaser',
            language='en',
        )
        followup = tarot_followup_prompt(
            question='What should I do next?',
            followup='Can you clarify?',
            cards_block='1. Current situation around the question - The Magician (upright)',
            last_answer='The first card points to action.',
            mode='teaser',
            language='en',
        )
        continuation = tarot_continuation_prompt(
            question='What should I do next?',
            first_card_line='The Magician (upright)',
            first_text='The first card points to action.',
            cards_block='2. Key obstacle or knot - The Tower (reversed)\n3. Advice and direction - Strength (upright)',
            language='en',
        )

        for prompt in (reading, followup, continuation):
            self.assertIn('Answer only in English', prompt)
            self.assertIn('SYSTEM INSTRUCTIONS:', prompt)
            self.assertIn('USER REQUEST:', prompt)
            self.assertNotIn('Отвечай только на русском языке', prompt)
            self.assertNotIn('СИСТЕМНЫЕ ИНСТРУКЦИИ:', prompt)
            self.assertNotIn('ЗАПРОС ПОЛЬЗОВАТЕЛЯ:', prompt)

    def test_prompt_text_has_no_mojibake_markers(self) -> None:
        prompt = '\n'.join(
            [
                tarot_reading_prompt(
                    'Что мне важно понять?',
                    '1. Текущая ситуация вокруг вопроса - Маг (прямая)',
                    mode='teaser',
                    language='ru',
                ),
                tarot_reading_prompt(
                    'What should I understand?',
                    '1. Current situation around the question - The Magician (upright)',
                    mode='teaser',
                    language='en',
                ),
            ]
        )

        for marker in ('В«', 'В»', 'вЂ', 'рџ'):
            self.assertNotIn(marker, prompt)


if __name__ == '__main__':
    unittest.main()
