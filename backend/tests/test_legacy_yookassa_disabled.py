from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.domain.billing_service import BillingService  # noqa: E402


class ConfiguredFakeYooKassaGateway:
    @property
    def is_configured(self) -> bool:
        return True


class FakeNotifier:
    pass


class LegacyYooKassaDisabledTests(unittest.IsolatedAsyncioTestCase):
    def _service(self, *, enabled: bool) -> BillingService:
        return BillingService(
            gateway=ConfiguredFakeYooKassaGateway(),  # type: ignore[arg-type]
            google_play_gateway=None,
            offer_url='https://example.com/terms',
            support_username='@support',
            support_max_url='https://max.example/support',
            return_url='https://example.com/return',
            test_mode=False,
            legacy_yookassa_enabled=enabled,
            notifier=FakeNotifier(),  # type: ignore[arg-type]
        )

    async def test_legacy_yookassa_is_disabled_by_default(self) -> None:
        service = self._service(enabled=False)

        self.assertFalse(service.is_configured)
        with self.assertRaisesRegex(RuntimeError, 'YooKassa is not configured'):
            await service.create_payment(
                client_id='client_disabled',
                plan_key='week',
            )

        self.assertEqual(await service.process_due_auto_renewals_once(), 0)

    async def test_legacy_yookassa_can_still_be_enabled_explicitly(self) -> None:
        service = self._service(enabled=True)

        self.assertTrue(service.is_configured)


if __name__ == '__main__':
    unittest.main()
