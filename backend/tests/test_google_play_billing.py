from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.domain.billing_service import BillingService  # noqa: E402
from src.domain.billing_plans import get_plan  # noqa: E402
from src.integrations.google_play_gateway import GooglePlayPurchaseInfo  # noqa: E402
from src.repositories import billing as billing_repo  # noqa: E402
from src.repositories.storage import init_storage  # noqa: E402


class FakeYooKassaGateway:
    @property
    def is_configured(self) -> bool:
        return False


class FakeGooglePlayGateway:
    is_configured = True

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def verify_purchase(
        self,
        *,
        package_name: str,
        product_id: str,
        purchase_token: str,
        recurring: bool,
    ) -> GooglePlayPurchaseInfo:
        self.calls.append(
            {
                'package_name': package_name,
                'product_id': product_id,
                'purchase_token': purchase_token,
                'recurring': recurring,
            }
        )
        status = 'failed' if purchase_token == 'token_failed' else 'paid'
        raw_state = (
            'SUBSCRIPTION_STATE_EXPIRED'
            if status == 'failed'
            else 'SUBSCRIPTION_STATE_ACTIVE'
        )
        return GooglePlayPurchaseInfo(
            product_id=product_id,
            purchase_token=purchase_token,
            order_id=f'order-{purchase_token}',
            status=status,
            expires_at='2099-01-01T00:00:00Z',
            auto_renewing=recurring,
            raw_state=raw_state,
        )


class FakeNotifier:
    def __init__(self) -> None:
        self.google_events: list[dict[str, object]] = []

    async def notify_google_play_purchase(self, **kwargs) -> None:
        self.google_events.append(kwargs)

    async def notify_subscription_canceled(self, client_id: str) -> None:
        return None

    async def notify_promo_redeemed(self, *, client_id: str, promo_code: str, tokens: int) -> None:
        return None


class GooglePlayBillingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir_context = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir_context.name) / 'billing.db'
        init_storage(db_path)
        self.google_gateway = FakeGooglePlayGateway()
        self.notifier = FakeNotifier()
        self.service = BillingService(
            gateway=FakeYooKassaGateway(),  # type: ignore[arg-type]
            google_play_gateway=self.google_gateway,  # type: ignore[arg-type]
            offer_url='https://example.com/terms',
            support_username='@support',
            support_max_url='https://max.example/support',
            return_url='https://example.com/return',
            test_mode=False,
            notifier=self.notifier,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.temp_dir_context.cleanup()

    async def test_valid_google_play_subscription_grants_entitlement(self) -> None:
        summary = await self.service.verify_google_play_purchase(
            client_id='client_google_1',
            product_id='weekly_readings',
            purchase_token='token_week_1',
            package_name='com.apptaro.app',
        )

        self.assertIsNotNone(summary.active_subscription)
        self.assertEqual(summary.active_subscription.remaining, 15)
        self.assertEqual(summary.active_subscription.provider, 'google_play')
        self.assertEqual(summary.active_subscription.auto_renew, 1)
        self.assertEqual(len(self.notifier.google_events), 1)

    async def test_one40_consumable_grants_40_readings(self) -> None:
        plan = get_plan('one40')
        self.assertEqual(plan.google_product_id, 'one40_readings')
        self.assertEqual(plan.limit, 40)

        summary = await self.service.verify_google_play_purchase(
            client_id='client_google_one40',
            product_id='one40_readings',
            purchase_token='token_one40',
            package_name='com.apptaro.app',
        )

        self.assertIsNotNone(summary.active_subscription)
        self.assertEqual(summary.active_subscription.remaining, 40)
        self.assertEqual(summary.active_subscription.provider, 'google_play')
        self.assertEqual(summary.active_subscription.auto_renew, 0)
        self.assertEqual(self.notifier.google_events[-1]['tokens'], 40)

    async def test_repeated_google_play_token_does_not_double_grant(self) -> None:
        await self.service.verify_google_play_purchase(
            client_id='client_google_2',
            product_id='weekly_readings',
            purchase_token='token_week_2',
            package_name='com.apptaro.app',
        )
        await self.service.verify_google_play_purchase(
            client_id='client_google_2',
            product_id='weekly_readings',
            purchase_token='token_week_2',
            package_name='com.apptaro.app',
        )

        active = billing_repo.get_active_subscription('client_google_2')
        self.assertIsNotNone(active)
        self.assertEqual(active.remaining, 15)
        self.assertEqual(len(self.notifier.google_events), 1)

    async def test_replayed_consumable_token_does_not_restore_new_client(self) -> None:
        await self.service.verify_google_play_purchase(
            client_id='client_google_pack_old',
            product_id='one10_readings',
            purchase_token='token_pack_replay',
            package_name='com.apptaro.app',
        )
        summary = await self.service.verify_google_play_purchase(
            client_id='client_google_pack_new',
            product_id='one10_readings',
            purchase_token='token_pack_replay',
            package_name='com.apptaro.app',
            restored=True,
        )

        self.assertIsNone(summary.active_subscription)
        self.assertIsNone(summary.latest_valid_subscription)
        self.assertEqual(len(self.notifier.google_events), 1)

    async def test_repeated_depleted_google_play_token_does_not_restore_same_client(self) -> None:
        await self.service.verify_google_play_purchase(
            client_id='client_google_depleted',
            product_id='weekly_readings',
            purchase_token='token_depleted',
            package_name='com.apptaro.app',
        )
        for _ in range(15):
            self.assertTrue(await self.service.consume_generation('client_google_depleted'))

        summary = await self.service.verify_google_play_purchase(
            client_id='client_google_depleted',
            product_id='weekly_readings',
            purchase_token='token_depleted',
            package_name='com.apptaro.app',
            restored=True,
        )

        self.assertIsNone(summary.active_subscription)
        self.assertEqual(len(self.notifier.google_events), 1)

    async def test_restore_existing_token_grants_new_client_entitlement(self) -> None:
        await self.service.verify_google_play_purchase(
            client_id='client_google_old',
            product_id='weekly_readings',
            purchase_token='token_restore',
            package_name='com.apptaro.app',
        )
        summary = await self.service.verify_google_play_purchase(
            client_id='client_google_new',
            product_id='weekly_readings',
            purchase_token='token_restore',
            package_name='com.apptaro.app',
            restored=True,
        )

        self.assertEqual(summary.active_subscription.provider, 'google_play')
        self.assertEqual(summary.active_subscription.remaining, 15)
        self.assertEqual(len(self.notifier.google_events), 2)
        self.assertTrue(self.notifier.google_events[-1]['restored'])

    async def test_failed_google_play_purchase_does_not_grant_entitlement(self) -> None:
        with self.assertRaises(ValueError):
            await self.service.verify_google_play_purchase(
                client_id='client_google_failed',
                product_id='weekly_readings',
                purchase_token='token_failed',
                package_name='com.apptaro.app',
            )

        self.assertIsNone(billing_repo.get_active_subscription('client_google_failed'))
        self.assertEqual(len(self.notifier.google_events), 0)


if __name__ == '__main__':
    unittest.main()
