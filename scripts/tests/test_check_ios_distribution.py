from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / 'scripts' / 'check_ios_distribution.py'


def _write_distribution_fixture(
    root: Path,
    *,
    build_number: int = 16,
    runner_bundle: str = 'com.nexwit.tarotreaderai',
    extra_bundle: str | None = None,
    allows_arbitrary_loads: bool = False,
) -> None:
    app = root / 'app'
    (app / 'ios' / 'Runner.xcodeproj').mkdir(parents=True)
    (app / 'ios' / 'Runner').mkdir(parents=True)
    (app / 'lib' / 'core' / 'config').mkdir(parents=True)
    (app / 'pubspec.yaml').write_text(
        f'version: 0.1.0+{build_number}\n',
        encoding='utf-8',
    )
    (app / 'ios' / 'Podfile').write_text(
        "platform :ios, '13.0'\n"
        "target 'Runner' do\n"
        "  flutter_install_all_ios_pods File.dirname(File.realpath(__FILE__))\n"
        "end\n",
        encoding='utf-8',
    )
    project = (
        f'PRODUCT_BUNDLE_IDENTIFIER = {runner_bundle};\n'
        'PRODUCT_BUNDLE_IDENTIFIER = com.nexwit.tarotreaderai.RunnerTests;\n'
    )
    if extra_bundle is not None:
        project += f'PRODUCT_BUNDLE_IDENTIFIER = {extra_bundle};\n'
    (app / 'ios' / 'Runner.xcodeproj' / 'project.pbxproj').write_text(
        project,
        encoding='utf-8',
    )
    ats = (
        '<key>NSAppTransportSecurity</key>'
        '<dict><key>NSAllowsArbitraryLoads</key><true/></dict>'
        if allows_arbitrary_loads
        else ''
    )
    (app / 'ios' / 'Runner' / 'Info.plist').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<plist version="1.0"><dict>'
        f'{ats}'
        '</dict></plist>',
        encoding='utf-8',
    )
    (app / 'lib' / 'core' / 'config' / 'app_config.dart').write_text(
        "static const String appleBackendBaseUrl = "
        "String.fromEnvironment('APPLE_BACKEND_BASE_URL');\n"
        "static const String applePrivacyPolicyUrl = "
        "String.fromEnvironment('APPLE_PRIVACY_POLICY_URL');\n",
        encoding='utf-8',
    )


def _run_checker(
    root: Path,
    *extra_args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), '--repo-root', str(root), *extra_args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_checker_accepts_valid_distribution_configuration(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_accepts_build_number_above_15(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path, build_number=17)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_build_number_15(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path, build_number=15)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 1
    assert 'greater than 15' in result.stdout


def test_checker_rejects_missing_apple_backend_url(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
        env={**os.environ, 'APPLE_BACKEND_BASE_URL': ''},
    )

    assert result.returncode == 1
    assert 'APPLE_BACKEND_BASE_URL' in result.stdout


def test_checker_rejects_non_https_apple_backend_url(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'http://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 1
    assert 'HTTPS' in result.stdout


@pytest.mark.parametrize(
    'origin',
    [
        ' https://api.example.test',
        'https://api.example.test ',
        'https://api .example.test',
        'https://user:pass@api.example.test',
        'https://api.example.test/v1',
        'https://api.example.test?debug=true',
        'https://api.example.test#fragment',
        'https://api.example.test:0',
        'https://api.example.test:65536',
        'https://api.example.test:abc',
    ],
)
def test_checker_rejects_invalid_apple_backend_origin(
    tmp_path: Path,
    origin: str,
) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        origin,
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 1
    assert 'HTTPS origin' in result.stdout


def test_checker_reads_apple_backend_url_from_environment(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)
    env = {
        **os.environ,
        'APPLE_BACKEND_BASE_URL': 'https://api.example.test',
        'APPLE_PRIVACY_POLICY_URL': 'https://example.test/privacy',
    }

    result = _run_checker(tmp_path, env=env)

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_wrong_bundle_identifier(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path, runner_bundle='com.apptaro.app')

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 1
    assert 'com.nexwit.tarotreaderai' in result.stdout


def test_checker_rejects_bad_extra_bundle_configuration(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path, extra_bundle='com.apptaro.app')

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 1
    assert 'com.apptaro.app' in result.stdout


def test_checker_rejects_broad_ats_exception(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path, allows_arbitrary_loads=True)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 1
    assert 'NSAllowsArbitraryLoads' in result.stdout


def test_repository_distribution_files_pass_with_injected_url() -> None:
    result = _run_checker(
        REPO_ROOT,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        'https://example.test/privacy',
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_missing_privacy_policy_url(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        env={**os.environ, 'APPLE_PRIVACY_POLICY_URL': ''},
    )

    assert result.returncode == 1
    assert 'APPLE_PRIVACY_POLICY_URL' in result.stdout


@pytest.mark.parametrize(
    'url',
    [
        ' https://example.test/privacy',
        'http://example.test/privacy',
        '/privacy',
        'https://user:pass@example.test/privacy',
        'https://example.test/privacy#section',
    ],
)
def test_checker_rejects_invalid_privacy_policy_url(
    tmp_path: Path,
    url: str,
) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
        '--apple-privacy-policy-url',
        url,
    )

    assert result.returncode == 1
    assert 'absolute HTTPS URL' in result.stdout
