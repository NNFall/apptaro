from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.repositories import admin as admin_repo  # noqa: E402
from src.repositories import billing as billing_repo  # noqa: E402
from src.repositories.storage import init_storage  # noqa: E402


class BillingPromoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir_context = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir_context.name) / 'billing.db'
        init_storage(db_path)

    def tearDown(self) -> None:
        self.temp_dir_context.cleanup()

    def test_invalid_promo_code_error_is_english(self) -> None:
        with self.assertRaisesRegex(ValueError, 'Invalid promo code'):
            billing_repo.redeem_promo_code('client_a', 'abc')

    def test_missing_promo_code_error_is_english(self) -> None:
        with self.assertRaisesRegex(LookupError, 'Promo code was not found'):
            billing_repo.redeem_promo_code('client_a', 'missing')

    def test_reused_promo_code_error_is_english(self) -> None:
        admin_repo.create_promo_code('ONCE', tokens=3, max_uses=1)
        self.assertEqual(billing_repo.redeem_promo_code('client_a', 'ONCE'), 3)

        with self.assertRaisesRegex(
            ValueError,
            'This promo code was already activated for this user',
        ):
            billing_repo.redeem_promo_code('client_a', 'ONCE')


if __name__ == '__main__':
    unittest.main()
