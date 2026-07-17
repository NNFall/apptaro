from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import urlparse


EXPECTED_APP_BUNDLE_ID = 'com.nexwit.tarot'
EXPECTED_TEST_BUNDLE_ID = 'com.nexwit.tarot.RunnerTests'


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Validate the repository configuration for iOS distribution.',
    )
    parser.add_argument(
        '--repo-root',
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument('--apple-backend-base-url')
    return parser.parse_args()


def _read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        errors.append(f'Missing required file: {path}')
        return ''


def _validate_backend_url(value: str, errors: list[str]) -> None:
    if not value:
        errors.append('APPLE_BACKEND_BASE_URL is required for Apple distribution.')
        return

    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        errors.append('APPLE_BACKEND_BASE_URL must be an absolute HTTPS URL.')


def validate(repo_root: Path, apple_backend_base_url: str) -> list[str]:
    errors: list[str] = []
    app_root = repo_root.resolve() / 'app'

    pubspec = _read(app_root / 'pubspec.yaml', errors)
    version_match = re.search(r'^version:\s*[^+\s]+\+(\d+)\s*$', pubspec, re.MULTILINE)
    if not version_match or version_match.group(1) != '16':
        errors.append('app/pubspec.yaml must use build number 16.')

    podfile = _read(app_root / 'ios' / 'Podfile', errors)
    if "platform :ios, '13.0'" not in podfile:
        errors.append("app/ios/Podfile must target iOS 13.0.")
    if 'flutter_install_all_ios_pods' not in podfile:
        errors.append('app/ios/Podfile must use the standard Flutter CocoaPods integration.')

    project = _read(
        app_root / 'ios' / 'Runner.xcodeproj' / 'project.pbxproj',
        errors,
    )
    if f'PRODUCT_BUNDLE_IDENTIFIER = {EXPECTED_APP_BUNDLE_ID};' not in project:
        errors.append(f'Runner bundle identifier must be {EXPECTED_APP_BUNDLE_ID}.')
    if f'PRODUCT_BUNDLE_IDENTIFIER = {EXPECTED_TEST_BUNDLE_ID};' not in project:
        errors.append(f'RunnerTests bundle identifier must be {EXPECTED_TEST_BUNDLE_ID}.')

    app_config = _read(app_root / 'lib' / 'core' / 'config' / 'app_config.dart', errors)
    if "String.fromEnvironment('APPLE_BACKEND_BASE_URL')" not in app_config:
        errors.append('AppConfig must read APPLE_BACKEND_BASE_URL at build time.')

    _validate_backend_url(apple_backend_base_url.strip(), errors)
    return errors


def main() -> int:
    args = _parse_args()
    backend_url = args.apple_backend_base_url
    if backend_url is None:
        backend_url = os.environ.get('APPLE_BACKEND_BASE_URL', '')

    errors = validate(args.repo_root, backend_url)
    if errors:
        print('iOS distribution configuration is invalid:')
        for error in errors:
            print(f'- {error}')
        return 1

    print('iOS distribution configuration is valid.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
