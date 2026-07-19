from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from appstoreserverlibrary.api_client import APIError, APIException
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import VerificationException, VerificationStatus
from requests import RequestException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.settings import get_settings  # noqa: E402
from src.core import dependencies  # noqa: E402
from src.integrations.app_store_gateway import (  # noqa: E402
    AppStoreGateway,
    AppStoreGatewayConfig,
    AppStoreGatewayError,
    AppStoreValidationError,
)


FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'apple' / 'transactions.json'
ALLOWED_PRODUCTS = frozenset({
    'weekly_readings',
    'monthly_readings',
    'one10_readings',
    'one40_readings',
})


class FakeClient:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def get_transaction_info(self, transaction_id: str) -> SimpleNamespace:
        self.calls.append(transaction_id)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return SimpleNamespace(signedTransactionInfo=self.outcome)


class FakeVerifier:
    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def verify_and_decode_signed_transaction(self, signed_transaction: str) -> object:
        self.calls.append(signed_transaction)
        payload = self.payloads[signed_transaction]
        if isinstance(payload, Exception):
            raise payload
        return payload


class AppStoreGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture_data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        self.production = _payload(fixture_data['production_weekly'])
        self.sandbox = _payload(fixture_data['sandbox_consumable'])

    def test_verifies_matching_bundle_product_transaction_and_environment(self) -> None:
        gateway, production_client, sandbox_client = self._gateway(
            production_outcome='signed-production-weekly',
        )

        result = gateway.get_verified_transaction('tx-production-weekly')

        self.assertEqual(result.transaction_id, 'tx-production-weekly')
        self.assertEqual(result.original_transaction_id, 'original-production-weekly')
        self.assertEqual(result.bundle_id, 'com.nexwit.tarotreaderai')
        self.assertEqual(result.product_id, 'weekly_readings')
        self.assertEqual(result.environment, Environment.PRODUCTION)
        self.assertEqual(result.signed_transaction, 'signed-production-weekly')
        self.assertEqual(production_client.calls, ['tx-production-weekly'])
        self.assertEqual(sandbox_client.calls, [])

    def test_retries_sandbox_only_when_production_transaction_is_not_found(self) -> None:
        not_found = APIException(404, APIError.TRANSACTION_ID_NOT_FOUND.value, 'not found')
        gateway, production_client, sandbox_client = self._gateway(
            production_outcome=not_found,
            sandbox_outcome='signed-sandbox-consumable',
        )

        result = gateway.get_verified_transaction('tx-sandbox-consumable')

        self.assertEqual(result.environment, Environment.SANDBOX)
        self.assertEqual(production_client.calls, ['tx-sandbox-consumable'])
        self.assertEqual(sandbox_client.calls, ['tx-sandbox-consumable'])

    def test_does_not_retry_sandbox_for_other_production_errors(self) -> None:
        rejected = APIException(401, 4010004, 'unauthorized')
        gateway, _, sandbox_client = self._gateway(production_outcome=rejected)

        with self.assertRaisesRegex(AppStoreGatewayError, 'Production'):
            gateway.get_verified_transaction('tx-production-weekly')

        self.assertEqual(sandbox_client.calls, [])

    def test_rejects_wrong_transaction_bundle_environment_and_unknown_product(self) -> None:
        invalid_payloads = (
            (_replace_payload(self.production, transactionId='different-id'), 'transaction'),
            (_replace_payload(self.production, bundleId='com.example.other'), 'bundle'),
            (_replace_payload(self.production, environment=Environment.SANDBOX), 'environment'),
            (_replace_payload(self.production, productId='unknown_product'), 'product'),
        )

        for payload, expected_error in invalid_payloads:
            with self.subTest(expected_error=expected_error):
                gateway, _, _ = self._gateway(
                    production_outcome='signed-invalid',
                    extra_payloads={'signed-invalid': payload},
                )
                with self.assertRaisesRegex(AppStoreValidationError, expected_error):
                    gateway.get_verified_transaction('tx-production-weekly')

    def test_rejects_revoked_or_expired_subscription_transaction(self) -> None:
        revoked = _replace_payload(self.production, revocationDate=1780000000000)
        expired = _replace_payload(self.production, expiresDate=946684800000)

        for payload, expected_error in ((revoked, 'revoked'), (expired, 'expired')):
            with self.subTest(expected_error=expected_error):
                gateway, _, _ = self._gateway(
                    production_outcome='signed-invalid',
                    extra_payloads={'signed-invalid': payload},
                )
                with self.assertRaisesRegex(AppStoreValidationError, expected_error):
                    gateway.get_verified_transaction('tx-production-weekly')

    def test_wraps_official_signature_verification_failure(self) -> None:
        failure = VerificationException(VerificationStatus.VERIFICATION_FAILURE)
        gateway, _, _ = self._gateway(
            production_outcome='signed-invalid',
            extra_payloads={'signed-invalid': failure},
        )

        with self.assertRaisesRegex(AppStoreValidationError, 'signature'):
            gateway.get_verified_transaction('tx-production-weekly')

    def test_maps_retryable_signature_verification_failure_to_gateway_error(self) -> None:
        failure = VerificationException(
            VerificationStatus.RETRYABLE_VERIFICATION_FAILURE,
        )
        gateway, _, _ = self._gateway(
            production_outcome='signed-invalid',
            extra_payloads={'signed-invalid': failure},
        )

        with self.assertRaisesRegex(AppStoreGatewayError, 'temporarily') as raised:
            gateway.get_verified_transaction('tx-production-weekly')

        self.assertNotIsInstance(raised.exception, AppStoreValidationError)

    def test_wraps_production_transport_failure_without_sandbox_fallback(self) -> None:
        gateway, _, sandbox_client = self._gateway(
            production_outcome=RequestException('TLS handshake failed'),
        )

        with self.assertRaisesRegex(AppStoreGatewayError, 'Production') as raised:
            gateway.get_verified_transaction('tx-production-weekly')

        self.assertNotIsInstance(raised.exception, AppStoreValidationError)
        self.assertEqual(sandbox_client.calls, [])

    def test_wraps_sandbox_transport_failure_after_not_found_fallback(self) -> None:
        not_found = APIException(404, APIError.TRANSACTION_ID_NOT_FOUND.value, 'not found')
        gateway, _, sandbox_client = self._gateway(
            production_outcome=not_found,
            sandbox_outcome=RequestException('DNS lookup failed'),
        )

        with self.assertRaisesRegex(AppStoreGatewayError, 'Sandbox') as raised:
            gateway.get_verified_transaction('tx-sandbox-consumable')

        self.assertNotIsInstance(raised.exception, AppStoreValidationError)
        self.assertEqual(sandbox_client.calls, ['tx-sandbox-consumable'])

    def test_builds_official_clients_and_verifiers_from_mounted_files(self) -> None:
        client_calls: list[tuple[bytes, str, str, str, Environment]] = []
        verifier_calls: list[tuple[list[bytes], bool, Environment, str, int | None]] = []

        def client_factory(*args: object) -> object:
            client_calls.append(args)  # type: ignore[arg-type]
            return FakeClient('unused')

        def verifier_factory(*args: object) -> object:
            verifier_calls.append(args)  # type: ignore[arg-type]
            return FakeVerifier({})

        with tempfile.TemporaryDirectory() as temp_dir:
            secrets_dir = Path(temp_dir)
            key_path = secrets_dir / 'AuthKey_TEST.p8'
            roots_dir = secrets_dir / 'roots'
            roots_dir.mkdir()
            key_path.write_bytes(b'private-key')
            (roots_dir / 'AppleRootCA-G3.cer').write_bytes(b'root-g3')
            (roots_dir / 'AppleRootCA-G2.cer').write_bytes(b'root-g2')

            AppStoreGateway(
                config=AppStoreGatewayConfig(
                    private_key_path=key_path,
                    key_id='KEY123',
                    issuer_id='issuer-123',
                    bundle_id='com.nexwit.tarotreaderai',
                    app_apple_id=1234567890,
                    root_certificates_dir=roots_dir,
                    enable_online_checks=True,
                    allowed_product_ids=ALLOWED_PRODUCTS,
                ),
                api_client_factory=client_factory,
                verifier_factory=verifier_factory,
            )

        self.assertEqual(
            client_calls,
            [
                (b'private-key', 'KEY123', 'issuer-123', 'com.nexwit.tarotreaderai', Environment.PRODUCTION),
                (b'private-key', 'KEY123', 'issuer-123', 'com.nexwit.tarotreaderai', Environment.SANDBOX),
            ],
        )
        self.assertEqual(
            verifier_calls,
            [
                ([b'root-g2', b'root-g3'], True, Environment.PRODUCTION, 'com.nexwit.tarotreaderai', 1234567890),
                ([b'root-g2', b'root-g3'], True, Environment.SANDBOX, 'com.nexwit.tarotreaderai', None),
            ],
        )

    def test_settings_load_app_store_credentials_and_defaults(self) -> None:
        env = {
            'APP_STORE_APPLE_ID': '1234567890',
            'APP_STORE_KEY_ID': 'KEY123',
            'APP_STORE_ISSUER_ID': 'issuer-123',
            'APP_STORE_PRIVATE_KEY_PATH': 'secrets/apple/AuthKey_TEST.p8',
            'APP_STORE_ROOT_CERTIFICATES_DIR': 'secrets/apple/roots',
            'APP_STORE_ENABLE_ONLINE_CHECKS': '1',
        }
        with patch.dict(os.environ, env, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        self.assertEqual(settings.app_store_bundle_id, 'com.nexwit.tarotreaderai')
        self.assertEqual(settings.app_store_app_apple_id, 1234567890)
        self.assertEqual(settings.app_store_key_id, 'KEY123')
        self.assertEqual(settings.app_store_issuer_id, 'issuer-123')
        self.assertTrue(settings.app_store_private_key_path.is_absolute())
        self.assertTrue(settings.app_store_root_certificates_dir.is_absolute())
        self.assertTrue(settings.app_store_enable_online_checks)
        get_settings.cache_clear()

    def test_dependency_treats_gateway_construction_error_as_unconfigured(self) -> None:
        settings = SimpleNamespace(
            app_store_key_id='KEY123',
            app_store_issuer_id='issuer-123',
            app_store_app_apple_id=1234567890,
            app_store_private_key_path=Path(__file__),
            app_store_root_certificates_dir=Path(__file__).parent,
            app_store_bundle_id='com.nexwit.tarotreaderai',
            app_store_enable_online_checks=False,
        )
        dependencies.get_app_store_gateway.cache_clear()
        try:
            with (
                patch.object(dependencies, 'get_settings', return_value=settings),
                patch.object(
                    dependencies,
                    'AppStoreGateway',
                    side_effect=AppStoreGatewayError('bad mounted key'),
                ),
            ):
                self.assertIsNone(dependencies.get_app_store_gateway())
        finally:
            dependencies.get_app_store_gateway.cache_clear()
    def test_rejects_an_expanded_product_allowlist(self) -> None:
        with self.assertRaisesRegex(ValueError, 'four App Store product ids'):
            AppStoreGateway.from_dependencies(
                bundle_id='com.nexwit.tarotreaderai',
                app_apple_id=1234567890,
                allowed_product_ids=ALLOWED_PRODUCTS | {'unreviewed_product'},
                production_client=FakeClient('unused'),
                sandbox_client=FakeClient('unused'),
                production_verifier=FakeVerifier({}),
                sandbox_verifier=FakeVerifier({}),
            )

    def _gateway(
        self,
        *,
        production_outcome: object,
        sandbox_outcome: object = 'signed-sandbox-consumable',
        extra_payloads: dict[str, object] | None = None,
    ) -> tuple[AppStoreGateway, FakeClient, FakeClient]:
        production_client = FakeClient(production_outcome)
        sandbox_client = FakeClient(sandbox_outcome)
        payloads: dict[str, object] = {
            'signed-production-weekly': self.production,
            'signed-sandbox-consumable': self.sandbox,
        }
        payloads.update(extra_payloads or {})
        gateway = AppStoreGateway.from_dependencies(
            bundle_id='com.nexwit.tarotreaderai',
            app_apple_id=1234567890,
            allowed_product_ids=ALLOWED_PRODUCTS,
            production_client=production_client,
            sandbox_client=sandbox_client,
            production_verifier=FakeVerifier(payloads),
            sandbox_verifier=FakeVerifier(payloads),
        )
        return gateway, production_client, sandbox_client


def _payload(data: dict[str, object]) -> SimpleNamespace:
    environment = Environment(data['environment'])
    return SimpleNamespace(
        transactionId=data.get('transactionId'),
        originalTransactionId=data.get('originalTransactionId'),
        bundleId=data.get('bundleId'),
        productId=data.get('productId'),
        appAccountToken=data.get('appAccountToken'),
        purchaseDate=data.get('purchaseDate'),
        expiresDate=data.get('expiresDate'),
        revocationDate=data.get('revocationDate'),
        environment=environment,
        type=data.get('type'),
    )


def _replace_payload(payload: SimpleNamespace, **changes: object) -> SimpleNamespace:
    values = vars(payload).copy()
    values.update(changes)
    return SimpleNamespace(**values)


if __name__ == '__main__':
    unittest.main()
