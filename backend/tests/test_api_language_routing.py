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
from src.integrations.text_generation import TextGenerationError  # noqa: E402
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

    async def consume_generation(self, client_id: str) -> bool:
        return True

    async def should_show_trial_teaser(self, client_id: str) -> bool:
        return False

    def mark_trial_teaser_used(self, client_id: str) -> None:
        return


class DenyBillingService:
    async def can_start_generation(self, client_id: str) -> bool:
        return False


class FailingRenderService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def render(self, **kwargs):
        raise self.error


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

    def test_job_limit_error_defaults_to_english_without_language_header(self) -> None:
        self.app.dependency_overrides[get_billing_service] = lambda: DenyBillingService()

        response = self.client.post(
            '/v1/presentations/jobs',
            json=self._render_payload(),
            headers={'X-Apptaro-Client-Id': 'apptaro_test_client'},
        )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(
            response.json()['detail'],
            'Your reading limit is over. Choose a subscription to continue.',
        )

    def test_job_limit_error_uses_russian_when_language_header_is_russian(self) -> None:
        self.app.dependency_overrides[get_billing_service] = lambda: DenyBillingService()

        response = self.client.post(
            '/v1/presentations/jobs',
            json=self._render_payload(),
            headers={
                'X-Apptaro-Client-Id': 'apptaro_test_client',
                'X-Apptaro-Language': 'ru',
            },
        )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(
            response.json()['detail'],
            'Лимит раскладов исчерпан. Выберите подписку, чтобы продолжить.',
        )

    def test_render_missing_asset_error_uses_russian_without_leaking_path(self) -> None:
        self.app.dependency_overrides[get_render_service] = lambda: FailingRenderService(
            FileNotFoundError('/data/runtime/tarot/cards/missing.png')
        )

        response = self.client.post(
            '/v1/presentations/render',
            json=self._render_payload(),
            headers={
                'X-Apptaro-Client-Id': 'apptaro_test_client',
                'X-Apptaro-Language': 'ru',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()['detail'],
            '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043d\u0430\u0439\u0442\u0438 \u043d\u0443\u0436\u043d\u044b\u0435 \u0444\u0430\u0439\u043b\u044b \u0434\u043b\u044f \u0440\u0430\u0441\u043a\u043b\u0430\u0434\u0430. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435.',
        )
        self.assertNotIn('/data/runtime', response.text)

    def test_render_text_generation_error_defaults_to_safe_english_message(self) -> None:
        self.app.dependency_overrides[get_render_service] = lambda: FailingRenderService(
            TextGenerationError('provider internal details')
        )

        response = self.client.post(
            '/v1/presentations/render',
            json=self._render_payload(),
            headers={'X-Apptaro-Client-Id': 'apptaro_test_client'},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()['detail'],
            'Failed to generate the tarot reading. Please try again.',
        )
        self.assertNotIn('provider internal details', response.text)

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

    def _render_payload(self) -> dict[str, object]:
        return {
            'topic': 'Career focus',
            'title': 'Reading: Career focus',
            'outline': ['Past: The Fool (upright)'],
            'design_id': 1,
            'generate_pdf': True,
        }


if __name__ == '__main__':
    unittest.main()
