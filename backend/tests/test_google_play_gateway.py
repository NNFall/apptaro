from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.integrations.google_play_gateway import GooglePlayGateway  # noqa: E402


class RecordingGooglePlayGateway(GooglePlayGateway):
    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__(package_name='com.apptaro.app')
        self.response = response
        self.urls: list[str] = []

    def _get_json(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        return self.response


class GooglePlayGatewayTests(unittest.TestCase):
    def test_rejects_package_name_mismatch_before_calling_google_api(self) -> None:
        gateway = RecordingGooglePlayGateway({})

        with self.assertRaisesRegex(ValueError, 'package name does not match'):
            gateway.verify_purchase(
                package_name='com.other.app',
                product_id='weekly_readings',
                purchase_token='token_123',
                recurring=True,
            )

        self.assertEqual(gateway.urls, [])

    def test_rejects_blank_product_id_and_purchase_token(self) -> None:
        gateway = RecordingGooglePlayGateway({})

        with self.assertRaisesRegex(ValueError, 'product id'):
            gateway.verify_purchase(
                package_name='com.apptaro.app',
                product_id='',
                purchase_token='token_123',
                recurring=True,
            )
        with self.assertRaisesRegex(ValueError, 'purchase token'):
            gateway.verify_purchase(
                package_name='com.apptaro.app',
                product_id='weekly_readings',
                purchase_token='',
                recurring=True,
            )

    def test_subscription_requires_matching_line_item_product(self) -> None:
        gateway = RecordingGooglePlayGateway({
            'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE',
            'latestOrderId': 'GPA.123',
            'lineItems': [{'productId': 'monthly_readings'}],
        })

        with self.assertRaisesRegex(ValueError, 'product does not match'):
            gateway.verify_purchase(
                package_name='com.apptaro.app',
                product_id='weekly_readings',
                purchase_token='token_weekly',
                recurring=True,
            )

    def test_active_subscription_parses_as_paid(self) -> None:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=14)
        ).isoformat().replace('+00:00', 'Z')
        gateway = RecordingGooglePlayGateway({
            'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE',
            'latestOrderId': 'GPA.456',
            'lineItems': [
                {
                    'productId': 'weekly_readings',
                    'expiryTime': expires_at,
                    'autoRenewingPlan': {},
                }
            ],
        })

        purchase = gateway.verify_purchase(
            package_name='com.apptaro.app',
            product_id='weekly_readings',
            purchase_token='token_weekly',
            recurring=True,
        )

        self.assertEqual(purchase.status, 'paid')
        self.assertEqual(purchase.order_id, 'GPA.456')
        self.assertEqual(purchase.expires_at, expires_at)
        self.assertTrue(purchase.auto_renewing)
        self.assertIn('/purchases/subscriptionsv2/tokens/token_weekly', gateway.urls[-1])

    def test_product_purchase_state_parses_paid_and_failed(self) -> None:
        paid_gateway = RecordingGooglePlayGateway({
            'purchaseState': 0,
            'orderId': 'GPA.ONE.1',
        })
        failed_gateway = RecordingGooglePlayGateway({
            'purchaseState': 1,
            'orderId': 'GPA.ONE.2',
        })

        paid = paid_gateway.verify_purchase(
            package_name='com.apptaro.app',
            product_id='one10_readings',
            purchase_token='token_one10',
            recurring=False,
        )
        failed = failed_gateway.verify_purchase(
            package_name='com.apptaro.app',
            product_id='one10_readings',
            purchase_token='token_one10_failed',
            recurring=False,
        )

        self.assertEqual(paid.status, 'paid')
        self.assertEqual(failed.status, 'failed')
        self.assertIn('/purchases/products/one10_readings/tokens/token_one10', paid_gateway.urls[-1])


if __name__ == '__main__':
    unittest.main()
