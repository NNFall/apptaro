from __future__ import annotations

import datetime as dt
import importlib.util
import plistlib
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / 'scripts' / 'macos' / 'release_profile_validator.py'
TEAM = 'TEAM123456'
BUNDLE = 'com.nexwit.tarot'
APPLICATION_IDENTIFIER = f'PREFIX123.{BUNDLE}'


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location('release_profile_validator', VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _write_plists(
    tmp_path: Path,
    *,
    profile_overrides: dict | None = None,
    profile_entitlement_overrides: dict | None = None,
    app_entitlement_overrides: dict | None = None,
) -> tuple[Path, Path]:
    profile_entitlements = {
        'application-identifier': APPLICATION_IDENTIFIER,
        'com.apple.developer.team-identifier': TEAM,
        'get-task-allow': False,
        **(profile_entitlement_overrides or {}),
    }
    profile = {
        'ApplicationIdentifierPrefix': ['PREFIX123'],
        'TeamIdentifier': [TEAM],
        'ExpirationDate': dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30),
        'Entitlements': profile_entitlements,
        **(profile_overrides or {}),
    }
    app_entitlements = {
        'application-identifier': APPLICATION_IDENTIFIER,
        'com.apple.developer.team-identifier': TEAM,
        'get-task-allow': False,
        **(app_entitlement_overrides or {}),
    }
    profile_path = tmp_path / 'profile.plist'
    app_path = tmp_path / 'app-entitlements.plist'
    profile_path.write_bytes(plistlib.dumps(profile))
    app_path.write_bytes(plistlib.dumps(app_entitlements))
    return profile_path, app_path


def test_distribution_profile_and_signed_entitlements_are_accepted(tmp_path: Path) -> None:
    profile, app = _write_plists(tmp_path)

    validator.validate_distribution_signing(profile, app, TEAM, BUNDLE)


@pytest.mark.parametrize(
    ('profile_overrides', 'profile_entitlements', 'app_entitlements', 'message'),
    [
        ({'ProvisionedDevices': ['DEVICE']}, None, None, 'ProvisionedDevices'),
        ({'ProvisionsAllDevices': True}, None, None, 'enterprise'),
        (None, {'get-task-allow': True}, None, 'get-task-allow'),
        (None, None, {'get-task-allow': True}, 'get-task-allow'),
        ({'TeamIdentifier': ['OTHERTEAM']}, None, None, 'TeamIdentifier'),
        (None, None, {'application-identifier': 'PREFIX123.other.bundle'}, 'application-identifier'),
    ],
)
def test_non_distribution_signing_is_rejected(
    tmp_path: Path,
    profile_overrides: dict | None,
    profile_entitlements: dict | None,
    app_entitlements: dict | None,
    message: str,
) -> None:
    profile, app = _write_plists(
        tmp_path,
        profile_overrides=profile_overrides,
        profile_entitlement_overrides=profile_entitlements,
        app_entitlement_overrides=app_entitlements,
    )

    with pytest.raises(validator.ProfileValidationError, match=message):
        validator.validate_distribution_signing(profile, app, TEAM, BUNDLE)


def test_expired_distribution_profile_is_rejected(tmp_path: Path) -> None:
    profile, app = _write_plists(
        tmp_path,
        profile_overrides={
            'ExpirationDate': dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1),
        },
    )

    with pytest.raises(validator.ProfileValidationError, match='expired'):
        validator.validate_distribution_signing(profile, app, TEAM, BUNDLE)
