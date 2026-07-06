from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core import dependencies  # noqa: E402
from src.core.settings import get_settings  # noqa: E402
from src.repositories.storage import init_storage  # noqa: E402


class GooglePlaySettingsTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        self._clear_caches()

    async def test_summary_test_mode_uses_google_play_flag_not_yookassa_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                "DATABASE_PATH": str(Path(temp_dir) / "billing.db"),
                "YOOKASSA_TEST_MODE": "1",
                "GOOGLE_PLAY_TEST_MODE": "0",
            }
            with patch.dict(os.environ, env, clear=True):
                self._clear_caches()
                init_storage(Path(env["DATABASE_PATH"]))

                service = dependencies.get_billing_service()
                summary = await service.get_summary("client_google_settings")

        self.assertFalse(summary.test_mode)

    def test_offer_url_defaults_empty_and_trims_configured_value(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self._clear_caches()
            self.assertEqual(get_settings().offer_url, "")

        with patch.dict(os.environ, {"OFFER_URL": " https://example.com/terms "}, clear=True):
            self._clear_caches()
            self.assertEqual(get_settings().offer_url, "https://example.com/terms")

    @staticmethod
    def _clear_caches() -> None:
        get_settings.cache_clear()
        dependencies.get_yookassa_gateway.cache_clear()
        dependencies.get_google_play_gateway.cache_clear()
        dependencies.get_billing_service.cache_clear()
        dependencies.get_admin_notifier.cache_clear()


if __name__ == "__main__":
    unittest.main()
