from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.deploy.deploy_backend_remote import (  # noqa: E402
    build_remote_env,
    ensure_admin_bot_token_is_configured,
    is_expected_health_response,
)


class DeployEnvironmentTests(unittest.TestCase):
    def test_google_play_deploy_does_not_reuse_legacy_offer_url(self) -> None:
        remote_env = build_remote_env(
            {
                'OFFER_URL': 'https://dimonk95.github.io/tarobotrustore/',
            },
            host_port=8022,
        )

        self.assertIn('OFFER_URL=\n', remote_env)
        self.assertNotIn('tarobotrustore', remote_env)

    def test_google_play_deploy_uses_explicit_google_play_offer_url(self) -> None:
        remote_env = build_remote_env(
            {
                'OFFER_URL': 'https://dimonk95.github.io/tarobotrustore/',
                'GOOGLE_PLAY_OFFER_URL': 'https://example.com/google-play-terms',
            },
            host_port=8022,
        )

        self.assertIn('OFFER_URL=https://example.com/google-play-terms\n', remote_env)
        self.assertNotIn('tarobotrustore', remote_env)

    def test_full_deploy_requires_admin_bot_token(self) -> None:
        remote_env = build_remote_env({}, host_port=8022)

        with self.assertRaisesRegex(RuntimeError, 'ADMIN_BOT_TOKEN'):
            ensure_admin_bot_token_is_configured(remote_env)

    def test_full_deploy_accepts_configured_admin_bot_token(self) -> None:
        remote_env = build_remote_env(
            {
                'ADMIN_BOT_TOKEN': '123456:unique-token',
            },
            host_port=8022,
        )

        ensure_admin_bot_token_is_configured(remote_env)

    def test_deploy_health_check_requires_pmapptaro_service(self) -> None:
        self.assertTrue(
            is_expected_health_response(
                '{"status":"ok","service":"PMapptaro Backend","environment":"production"}'
            )
        )
        self.assertFalse(
            is_expected_health_response(
                '{"status":"ok","service":"Other Backend","environment":"production"}'
            )
        )

    def test_deploy_health_check_rejects_non_json_response(self) -> None:
        self.assertFalse(is_expected_health_response('ok'))


if __name__ == '__main__':
    unittest.main()
