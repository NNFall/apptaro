from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dev.google_play_readiness import (  # noqa: E402
    CheckResult,
    collect_local_checks,
    duplicate_admin_token_paths,
    overall_exit_code,
)


class GooglePlayReadinessTests(unittest.TestCase):
    def test_collect_local_checks_accepts_expected_google_play_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app' / 'android' / 'app').mkdir(parents=True)
            (root / 'app' / 'lib' / 'core' / 'config').mkdir(parents=True)
            (root / 'app' / 'build' / 'app' / 'outputs' / 'bundle' / 'release').mkdir(parents=True)
            (root / 'app' / 'build' / 'app' / 'outputs' / 'flutter-apk').mkdir(parents=True)

            (root / 'app' / 'pubspec.yaml').write_text('version: 0.1.0+12\n', encoding='utf-8')
            (root / 'app' / 'android' / 'app' / 'build.gradle.kts').write_text(
                'android {\n'
                '    namespace = "com.apptaro.app"\n'
                '    defaultConfig {\n'
                '        applicationId = "com.apptaro.app"\n'
                '    }\n'
                '}\n',
                encoding='utf-8',
            )
            (root / 'app' / 'lib' / 'core' / 'config' / 'app_config.dart').write_text(
                "class AppConfig {\n"
                "  static const String fixedBackendBaseUrl = 'http://185.171.83.116:8022';\n"
                "  static const String androidPackageName = 'com.apptaro.app';\n"
                "}\n",
                encoding='utf-8',
            )
            (root / 'app' / 'build' / 'app' / 'outputs' / 'bundle' / 'release' / 'app-release.aab').write_bytes(b'aab')
            (root / 'app' / 'build' / 'app' / 'outputs' / 'flutter-apk' / 'app-release.apk').write_bytes(b'apk')

            checks = collect_local_checks(root)

        self.assertTrue(all(item.ok for item in checks), checks)

    def test_collect_local_checks_reports_wrong_package_and_missing_aab(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app' / 'android' / 'app').mkdir(parents=True)
            (root / 'app' / 'lib' / 'core' / 'config').mkdir(parents=True)
            (root / 'app' / 'build' / 'app' / 'outputs' / 'flutter-apk').mkdir(parents=True)

            (root / 'app' / 'pubspec.yaml').write_text('version: 0.1.0+12\n', encoding='utf-8')
            (root / 'app' / 'android' / 'app' / 'build.gradle.kts').write_text(
                'namespace = "com.example.wrong"\n'
                'applicationId = "com.example.wrong"\n',
                encoding='utf-8',
            )
            (root / 'app' / 'lib' / 'core' / 'config' / 'app_config.dart').write_text(
                "static const String fixedBackendBaseUrl = 'http://185.171.83.116:8022';\n",
                encoding='utf-8',
            )
            (root / 'app' / 'build' / 'app' / 'outputs' / 'flutter-apk' / 'app-release.apk').write_bytes(b'apk')

            checks = collect_local_checks(root)

        failed_names = {item.name for item in checks if not item.ok}
        self.assertIn('android package', failed_names)
        self.assertIn('release AAB artifact', failed_names)

    def test_duplicate_admin_token_paths_ignores_current_project_path(self) -> None:
        paths = duplicate_admin_token_paths(
            {
                '/root/PMapptaro/.env': 'abc123',
                '/root/apptaro/.env': 'abc123',
                '/root/appslides/.env': 'def456',
            },
            current_project_env='/root/PMapptaro/.env',
        )

        self.assertEqual(paths, ['/root/apptaro/.env'])

    def test_overall_exit_code_is_nonzero_when_any_required_check_fails(self) -> None:
        checks = [
            CheckResult(name='ok', ok=True, detail='ready'),
            CheckResult(name='bad', ok=False, detail='broken'),
        ]

        self.assertEqual(overall_exit_code(checks), 1)


if __name__ == '__main__':
    unittest.main()
