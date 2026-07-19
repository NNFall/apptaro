from __future__ import annotations

import argparse
import os
import plistlib
import re
from pathlib import Path
from urllib.parse import urlparse


EXPECTED_APP_BUNDLE_ID = 'com.nexwit.tarotreaderai'
EXPECTED_TEST_BUNDLE_ID = 'com.nexwit.tarotreaderai.RunnerTests'


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
    parser.add_argument('--apple-privacy-policy-url')
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

    invalid = value != value.strip() or any(character.isspace() for character in value)
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError:
        port = None
        invalid = True

    invalid = invalid or any(
        (
            parsed.scheme != 'https',
            not parsed.hostname,
            parsed.username is not None,
            parsed.password is not None,
            parsed.path not in ('', '/'),
            bool(parsed.params),
            bool(parsed.query),
            bool(parsed.fragment),
            port is not None and not 1 <= port <= 65535,
        )
    )
    if invalid:
        errors.append(
            'APPLE_BACKEND_BASE_URL must be exactly one HTTPS origin.',
        )


def _validate_privacy_policy_url(value: str, errors: list[str]) -> None:
    if not value:
        errors.append(
            'APPLE_PRIVACY_POLICY_URL is required for Apple distribution.',
        )
        return

    invalid = value != value.strip() or any(character.isspace() for character in value)
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError:
        port = None
        invalid = True

    invalid = invalid or any(
        (
            parsed.scheme != 'https',
            not parsed.hostname,
            parsed.username is not None,
            parsed.password is not None,
            bool(parsed.fragment),
            port is not None and not 1 <= port <= 65535,
        )
    )
    if invalid:
        errors.append(
            'APPLE_PRIVACY_POLICY_URL must be an absolute HTTPS URL.',
        )


def validate(
    repo_root: Path,
    apple_backend_base_url: str,
    apple_privacy_policy_url: str,
) -> list[str]:
    errors: list[str] = []
    app_root = repo_root.resolve() / 'app'

    pubspec = _read(app_root / 'pubspec.yaml', errors)
    version_match = re.search(r'^version:\s*[^+\s]+\+(\d+)\s*$', pubspec, re.MULTILINE)
    if not version_match or int(version_match.group(1)) <= 15:
        errors.append('app/pubspec.yaml build number must be greater than 15.')

    podfile = _read(app_root / 'ios' / 'Podfile', errors)
    if "platform :ios, '13.0'" not in podfile:
        errors.append("app/ios/Podfile must target iOS 13.0.")
    if 'flutter_install_all_ios_pods' not in podfile:
        errors.append('app/ios/Podfile must use the standard Flutter CocoaPods integration.')

    project = _read(
        app_root / 'ios' / 'Runner.xcodeproj' / 'project.pbxproj',
        errors,
    )
    bundle_ids = re.findall(
        r'PRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^;\s]+)\s*;',
        project,
    )
    if EXPECTED_APP_BUNDLE_ID not in bundle_ids:
        errors.append(f'Runner bundle identifier must be {EXPECTED_APP_BUNDLE_ID}.')
    if EXPECTED_TEST_BUNDLE_ID not in bundle_ids:
        errors.append(f'RunnerTests bundle identifier must be {EXPECTED_TEST_BUNDLE_ID}.')
    for bundle_id in bundle_ids:
        if bundle_id not in (EXPECTED_APP_BUNDLE_ID, EXPECTED_TEST_BUNDLE_ID):
            errors.append(f'Unexpected iOS bundle identifier: {bundle_id}.')

    info_plist_path = app_root / 'ios' / 'Runner' / 'Info.plist'
    info_plist_source = _read(info_plist_path, errors)
    if info_plist_source:
        try:
            info_plist = plistlib.loads(info_plist_source.encode('utf-8'))
        except plistlib.InvalidFileException:
            errors.append(f'Invalid property list: {info_plist_path}')
        else:
            transport_security = info_plist.get('NSAppTransportSecurity', {})
            if (
                isinstance(transport_security, dict)
                and transport_security.get('NSAllowsArbitraryLoads') is True
            ):
                errors.append('NSAllowsArbitraryLoads must not be enabled.')

    app_config = _read(app_root / 'lib' / 'core' / 'config' / 'app_config.dart', errors)
    if "String.fromEnvironment('APPLE_BACKEND_BASE_URL')" not in app_config:
        errors.append('AppConfig must read APPLE_BACKEND_BASE_URL at build time.')
    if "String.fromEnvironment('APPLE_PRIVACY_POLICY_URL')" not in app_config:
        errors.append(
            'AppConfig must read APPLE_PRIVACY_POLICY_URL at build time.',
        )

    _validate_backend_url(apple_backend_base_url, errors)
    _validate_privacy_policy_url(apple_privacy_policy_url, errors)
    return errors


def main() -> int:
    args = _parse_args()
    backend_url = args.apple_backend_base_url
    if backend_url is None:
        backend_url = os.environ.get('APPLE_BACKEND_BASE_URL', '')
    privacy_policy_url = args.apple_privacy_policy_url
    if privacy_policy_url is None:
        privacy_policy_url = os.environ.get('APPLE_PRIVACY_POLICY_URL', '')

    errors = validate(args.repo_root, backend_url, privacy_policy_url)
    if errors:
        print('iOS distribution configuration is invalid:')
        for error in errors:
            print(f'- {error}')
        return 1

    print('iOS distribution configuration is valid.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
