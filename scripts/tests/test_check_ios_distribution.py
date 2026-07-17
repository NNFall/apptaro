from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / 'scripts' / 'check_ios_distribution.py'


def _write_distribution_fixture(root: Path, *, runner_bundle: str = 'com.nexwit.tarot') -> None:
    app = root / 'app'
    (app / 'ios' / 'Runner.xcodeproj').mkdir(parents=True)
    (app / 'lib' / 'core' / 'config').mkdir(parents=True)
    (app / 'pubspec.yaml').write_text('version: 0.1.0+16\n', encoding='utf-8')
    (app / 'ios' / 'Podfile').write_text(
        "platform :ios, '13.0'\n"
        "target 'Runner' do\n"
        "  flutter_install_all_ios_pods File.dirname(File.realpath(__FILE__))\n"
        "end\n",
        encoding='utf-8',
    )
    (app / 'ios' / 'Runner.xcodeproj' / 'project.pbxproj').write_text(
        f'PRODUCT_BUNDLE_IDENTIFIER = {runner_bundle};\n'
        'PRODUCT_BUNDLE_IDENTIFIER = com.nexwit.tarot.RunnerTests;\n',
        encoding='utf-8',
    )
    (app / 'lib' / 'core' / 'config' / 'app_config.dart').write_text(
        "static const String appleBackendBaseUrl = "
        "String.fromEnvironment('APPLE_BACKEND_BASE_URL');\n",
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
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_missing_apple_backend_url(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(tmp_path, env={**os.environ, 'APPLE_BACKEND_BASE_URL': ''})

    assert result.returncode == 1
    assert 'APPLE_BACKEND_BASE_URL' in result.stdout


def test_checker_rejects_non_https_apple_backend_url(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'http://api.example.test',
    )

    assert result.returncode == 1
    assert 'HTTPS' in result.stdout


def test_checker_reads_apple_backend_url_from_environment(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path)
    env = {**os.environ, 'APPLE_BACKEND_BASE_URL': 'https://api.example.test'}

    result = _run_checker(tmp_path, env=env)

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_wrong_bundle_identifier(tmp_path: Path) -> None:
    _write_distribution_fixture(tmp_path, runner_bundle='com.apptaro.app')

    result = _run_checker(
        tmp_path,
        '--apple-backend-base-url',
        'https://api.example.test',
    )

    assert result.returncode == 1
    assert 'com.nexwit.tarot' in result.stdout


def test_repository_distribution_files_pass_with_injected_url() -> None:
    result = _run_checker(
        REPO_ROOT,
        '--apple-backend-base-url',
        'https://api.example.test',
    )

    assert result.returncode == 0, result.stdout + result.stderr
