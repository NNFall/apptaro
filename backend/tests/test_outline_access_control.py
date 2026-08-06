from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.dependencies import (  # noqa: E402
    get_admin_notifier,
    get_billing_service,
    get_known_client_id,
    get_outline_service,
    get_render_service,
)
from src.domain.presentation_outline_service import OutlineResult  # noqa: E402
from src.integrations.admin_notifier import AdminNotifier  # noqa: E402
from src.main import create_app  # noqa: E402


LIMIT_MESSAGE = 'Your reading limit is over. Choose a subscription to continue.'


class ReturningUnpaidBillingService:
    async def should_show_trial_teaser(self, client_id: str) -> bool:
        return False

    async def can_start_generation(self, client_id: str) -> bool:
        return False


class NewUnpaidBillingService:
    def __init__(self) -> None:
        self.marked_used = False

    async def should_show_trial_teaser(self, client_id: str) -> bool:
        return True

    async def can_start_generation(self, client_id: str) -> bool:
        raise AssertionError('A first teaser must not require a paid balance')

    def mark_trial_teaser_used(self, client_id: str) -> None:
        self.marked_used = True


class PaidBillingService:
    async def should_show_trial_teaser(self, client_id: str) -> bool:
        return False

    async def can_start_generation(self, client_id: str) -> bool:
        return True


class RecordingOutlineService:
    def __init__(self) -> None:
        self.generate_calls = 0
        self.revise_calls = 0

    async def generate(self, topic: str, slides_total: int, **kwargs) -> OutlineResult:
        self.generate_calls += 1
        cards_count = kwargs.get('cards_count', 3)
        outline = ['Card 1'] if cards_count == 1 else ['Card 1', 'Card 2', 'Card 3']
        return OutlineResult(
            title='Recorded outline',
            outline=outline,
            slides_total=slides_total,
            content_slides=len(outline),
        )

    async def revise(
        self,
        topic: str,
        slides_total: int,
        outline: list[str],
        comment: str,
        **kwargs,
    ) -> OutlineResult:
        self.revise_calls += 1
        return OutlineResult(
            title='Unexpected revised outline',
            outline=['Card 1', 'Card 2', 'Card 3'],
            slides_total=slides_total,
            content_slides=3,
        )


class OutlineAccessControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.outline_service = RecordingOutlineService()
        app = create_app()
        app.dependency_overrides[get_known_client_id] = lambda: 'at_returning_unpaid'
        app.dependency_overrides[get_billing_service] = lambda: ReturningUnpaidBillingService()
        app.dependency_overrides[get_outline_service] = lambda: self.outline_service
        app.dependency_overrides[get_render_service] = object
        app.dependency_overrides[get_admin_notifier] = lambda: AdminNotifier(bot_token='', admin_ids=[])
        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()

    def test_returning_unpaid_client_cannot_generate_three_card_outline(self) -> None:
        response = self.client.post(
            '/v1/presentations/outline',
            json={'topic': 'Will I find a new job?', 'slides_total': 4},
        )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()['detail'], LIMIT_MESSAGE)
        self.assertEqual(self.outline_service.generate_calls, 0)

    def test_returning_unpaid_client_cannot_revise_outline(self) -> None:
        response = self.client.post(
            '/v1/presentations/outline/revise',
            json={
                'topic': 'Will I find a new job?',
                'slides_total': 4,
                'outline': ['Card 1', 'Card 2', 'Card 3'],
                'comment': 'Draw different cards',
                'title': 'Career reading',
            },
        )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()['detail'], LIMIT_MESSAGE)
        self.assertEqual(self.outline_service.revise_calls, 0)

    def test_new_unpaid_client_still_receives_one_card_teaser(self) -> None:
        billing_service = NewUnpaidBillingService()
        self.app.dependency_overrides[get_billing_service] = lambda: billing_service

        response = self.client.post(
            '/v1/presentations/outline',
            json={'topic': 'Will I find a new job?', 'slides_total': 4},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['teaser_mode'])
        self.assertEqual(response.json()['outline'], ['Card 1'])
        self.assertTrue(billing_service.marked_used)

    def test_paid_client_still_receives_three_card_outline(self) -> None:
        self.app.dependency_overrides[get_billing_service] = lambda: PaidBillingService()

        response = self.client.post(
            '/v1/presentations/outline',
            json={'topic': 'Will I find a new job?', 'slides_total': 4},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['teaser_mode'])
        self.assertEqual(response.json()['outline'], ['Card 1', 'Card 2', 'Card 3'])


if __name__ == '__main__':
    unittest.main()
