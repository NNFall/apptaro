from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.api.billing import router as billing_router  # noqa: E402


class GooglePlayApiSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(billing_router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_redirect_payment_creation_is_disabled(self) -> None:
        response = self.client.post(
            '/v1/billing/payments',
            json={'plan_key': 'week', 'context': 'new'},
        )

        self.assertEqual(response.status_code, 410)
        self.assertIn('Google Play', response.json()['detail'])

    def test_redirect_payment_polling_is_disabled(self) -> None:
        response = self.client.get('/v1/billing/payments/payment_123')

        self.assertEqual(response.status_code, 410)
        self.assertIn('google-play/verify', response.json()['detail'])


if __name__ == '__main__':
    unittest.main()
