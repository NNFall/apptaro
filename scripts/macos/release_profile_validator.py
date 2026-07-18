#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import plistlib
import sys
from pathlib import Path
from typing import Any, Sequence


class ProfileValidationError(RuntimeError):
    pass


def _load_plist(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open('rb') as stream:
            payload = plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException) as exc:
        raise ProfileValidationError(f'{label} is not a readable plist: {exc}') from exc
    if not isinstance(payload, dict):
        raise ProfileValidationError(f'{label} must contain a plist dictionary.')
    return payload


def validate_distribution_signing(
    profile_path: Path | str,
    app_entitlements_path: Path | str,
    expected_team: str,
    expected_bundle: str,
    *,
    now: dt.datetime | None = None,
) -> None:
    profile = _load_plist(Path(profile_path), 'embedded provisioning profile')
    app_entitlements = _load_plist(Path(app_entitlements_path), 'signed app entitlements')
    profile_entitlements = profile.get('Entitlements') or {}
    if not isinstance(profile_entitlements, dict):
        raise ProfileValidationError('profile Entitlements must be a dictionary.')

    errors: list[str] = []
    team_ids = profile.get('TeamIdentifier') or []
    prefixes = profile.get('ApplicationIdentifierPrefix') or []
    profile_team = profile_entitlements.get('com.apple.developer.team-identifier')
    application_identifier = profile_entitlements.get('application-identifier')

    if expected_team not in team_ids or profile_team != expected_team:
        errors.append('profile TeamIdentifier does not match the selected Xcode development team')
    if not isinstance(application_identifier, str) or not any(
        application_identifier == f'{prefix}.{expected_bundle}' for prefix in prefixes
    ):
        errors.append('profile application-identifier does not match its prefix and Bundle ID')
    if profile_entitlements.get('get-task-allow') is not False:
        errors.append('profile get-task-allow must be false for App Store distribution')
    if profile.get('ProvisionedDevices'):
        errors.append('profile contains ProvisionedDevices and is not an App Store distribution profile')
    if profile.get('ProvisionsAllDevices'):
        errors.append('enterprise ProvisionsAllDevices profile is not allowed')

    expiration = profile.get('ExpirationDate')
    if not isinstance(expiration, dt.datetime):
        errors.append('profile ExpirationDate is missing')
    else:
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=dt.timezone.utc)
        current_time = now or dt.datetime.now(dt.timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=dt.timezone.utc)
        if expiration <= current_time:
            errors.append('distribution profile is expired')

    if app_entitlements.get('com.apple.developer.team-identifier') != expected_team:
        errors.append('signed app team identifier does not match the selected Xcode team')
    if app_entitlements.get('application-identifier') != application_identifier:
        errors.append('signed app application-identifier does not match the embedded profile')
    if app_entitlements.get('get-task-allow') is not False:
        errors.append('signed app get-task-allow must be false')

    if errors:
        raise ProfileValidationError('; '.join(errors))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate App Store distribution signing plists.')
    parser.add_argument('--profile-plist', type=Path, required=True)
    parser.add_argument('--app-entitlements-plist', type=Path, required=True)
    parser.add_argument('--expected-team', required=True)
    parser.add_argument('--expected-bundle', required=True)
    args = parser.parse_args(argv)
    try:
        validate_distribution_signing(
            args.profile_plist,
            args.app_entitlements_plist,
            args.expected_team,
            args.expected_bundle,
        )
    except ProfileValidationError as exc:
        print(f'ERROR: IPA distribution signing validation failed: {exc}', file=sys.stderr)
        return 1
    print('Embedded App Store distribution profile and signed entitlements passed validation.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
