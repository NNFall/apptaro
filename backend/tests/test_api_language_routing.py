from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.dependencies import (  # noqa: E402
    get_admin_notifier,
    get_billing_service,
    get_outline_service,
    get_render_service,
)
from src.domain.presentation_outline_service import PresentationOutlineService  # noqa: E402
from src.integrations.admin_notifier import AdminNotifier  # noqa: E402
from src.main import create_app  # noqa: E402


class RecordingGenerationClient:
    def __init__(self) -> None:
        self.title_languages: list[str] = []

    def generate_title(self, topic: str, *, language: str = 'en') -> str:
        self.title_languages.append(language)
        if language == 'en':
            return f'Reading: {topic}'
        return f'Расклад: {topic}'


class AllowBillingService:
    async def can_start_generation(self, client_id: str) -> bool:
        return True

    async def should_show_trial_teaser(self, client_id: str) -> bool:
        return False

    def mark_trial_teaser_used(self, client_id: str) -> None:
        return


class BackendLanguageRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir_context = tempfile.TemporaryDirectory()
        self.generation_client = RecordingGenerationClient()
        app = create_app()
        app.dependency_overrides[get_outline_service] = lambda: PresentationOutlineService(
            self.generation_client,
            cards_dir=BACKEND_DIR / 'runtime' / 'tarot' / 'cards',
        )
        app.dependency_overrides[get_render_service] = object
        app.dependency_overrides[get_billing_service] = lambda: AllowBillingService()
        app.dependency_overrides[get_admin_notifier] = lambda: AdminNotifier(bot_token='', admin_ids=[])

        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.temp_dir_context.cleanup()

    def test_outline_defaults_to_english_without_language_header(self) -> None:
        payload = self._outline(topic='Career focus')

        self.assertEqual(payload['title'], 'Reading: Career focus')
        self.assertEqual(self.generation_client.title_languages[-1], 'en')
        self.assertRegex(payload['outline'][0], r'\((upright|reversed)\)')
        self.assertNotIn('прямая', payload['outline'][0])

    def test_outline_uses_russian_when_language_header_is_russian(self) -> None:
        payload = self._outline(topic='Тестовая тема', language='ru')

        self.assertEqual(payload['title'], 'Расклад: Тестовая тема')
        self.assertEqual(self.generation_client.title_languages[-1], 'ru')
        self.assertRegex(payload['outline'][0], r'\((прямая|перевернутая)\)')

    def _outline(self, *, topic: str, language: str | None = None) -> dict[str, object]:
        headers = {
            'X-Apptaro-Client-Id': 'apptaro_test_client',
        }
        if language:
            headers['X-Apptaro-Language'] = language
        response = self.client.post(
            '/v1/presentations/outline',
            json={
                'topic': topic,
                'slides_total': 6,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()


if __name__ == '__main__':
    unittest.main()
