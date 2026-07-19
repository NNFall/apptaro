from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = REPO_ROOT / 'scripts' / 'macos' / 'bootstrap_ios.sh'
BUILD = REPO_ROOT / 'scripts' / 'macos' / 'build_testflight.sh'
RUNBOOK = REPO_ROOT / 'docs' / 'APP_STORE_RELEASE.md'
XCODE_PROJECT = REPO_ROOT / 'app' / 'ios' / 'Runner.xcodeproj' / 'project.pbxproj'
IOS_INFO_PLIST = REPO_ROOT / 'app' / 'ios' / 'Runner' / 'Info.plist'
EXPORT_OPTIONS_PLIST = REPO_ROOT / 'app' / 'ios' / 'ExportOptions.plist'
LAUNCH_SCREEN = REPO_ROOT / 'app' / 'ios' / 'Runner' / 'Base.lproj' / 'LaunchScreen.storyboard'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_macos_scripts_have_strict_portable_shell_contract() -> None:
    probe_script = REPO_ROOT / 'scripts' / 'macos' / 'release_url_probe.py'
    profile_script = REPO_ROOT / 'scripts' / 'macos' / 'release_profile_validator.py'
    runtime_script = REPO_ROOT / 'scripts' / 'macos' / 'release_runtime_check.py'
    for script in (BOOTSTRAP, BUILD):
        content = _read(script)
        assert content.startswith('#!/usr/bin/env bash\nset -euo pipefail\n')
        assert 'BASH_SOURCE[0]' in content
        assert 'C:\\' not in content
        assert '\r\n' not in content
        assert 'mapfile' not in content
    assert probe_script.read_text(encoding='utf-8').startswith('#!/usr/bin/env python3\n')
    assert profile_script.read_text(encoding='utf-8').startswith('#!/usr/bin/env python3\n')
    assert runtime_script.read_text(encoding='utf-8').startswith('#!/usr/bin/env python3\n')


def test_bootstrap_checks_toolchain_and_preserves_dirty_work() -> None:
    content = _read(BOOTSTRAP)

    for command in (
        'sw_vers',
        'xcodebuild -version',
        'xcrun --sdk iphoneos --show-sdk-version',
        'flutter --version',
        'pod --version',
        'python3 --version',
        'flutter pub get',
        'pod install',
        'flutter analyze',
        'flutter test',
        'python3 -m pytest backend/tests -q',
    ):
        assert command in content

    assert 'codex/apple-app-store' in content
    assert 'status --porcelain' in content
    assert 'git reset' not in content
    assert 'git clean' not in content
    assert 'Runner.xcworkspace' in content
    assert "channel != 'stable'" in content
    assert 'Podfile.lock' in content
    assert 'pod install --deployment' in content
    assert 'ls-files --error-unmatch' in content
    assert 'release_runtime_check.py' in content


def test_build_validates_release_inputs_and_artifact() -> None:
    content = _read(BUILD)
    profile_validator = _read(
        REPO_ROOT / 'scripts' / 'macos' / 'release_profile_validator.py',
    )

    assert 'APPLE_BACKEND_BASE_URL' in content
    assert 'APPLE_PRIVACY_POLICY_URL' in content
    assert 'export LANG="${LANG:-en_US.UTF-8}"' in content
    assert 'export LC_ALL="${LC_ALL:-en_US.UTF-8}"' in content
    assert 'https://' in content
    assert '--build-name' in content
    assert '--build-number' in content
    assert 'com.nexwit.tarotreaderai' in content
    assert 'status --porcelain -- app' in content
    assert content.count('status --porcelain -- app') >= 2
    assert 'flutter clean' in content
    assert 'flutter build ipa --release' in content
    assert '--export-options-plist "$export_options_plist"' in content
    assert '--dart-define=APPLE_BACKEND_BASE_URL=' in content
    assert '--dart-define=APPLE_PRIVACY_POLICY_URL=' in content
    assert 'Payload' in content
    assert 'CFBundleIdentifier' in content
    assert 'CFBundleShortVersionString' in content
    assert 'CFBundleVersion' in content
    assert 'Transporter' in content
    assert 'TestFlight' in content
    assert 'altool' not in content
    assert 'release_url_probe.py' in content
    assert '--timeout-seconds' in content
    assert 'codesign --verify --deep --strict' in content
    assert 'security cms -D -i' in content
    assert 'embedded.mobileprovision' in content
    assert 'release_profile_validator.py' in content
    assert 'release_runtime_check.py' in content
    assert 'get-task-allow' in profile_validator
    assert 'application-identifier' in profile_validator
    assert 'Podfile.lock' in content
    assert 'pod install --deployment' in content
    assert "channel != 'stable'" in content
    assert 'Dependency resolution changed files inside app/' in content


def test_app_store_export_options_pin_manual_distribution_profile() -> None:
    content = _read(EXPORT_OPTIONS_PLIST)

    for expected in (
        '<string>app-store-connect</string>',
        '<key>com.nexwit.tarotreaderai</key>',
        '<string>Tarot Reader AI App Store 2026</string>',
        '<string>Apple Distribution</string>',
        '<string>manual</string>',
        '<string>WH73RJDJXC</string>',
    ):
        assert expected in content


def test_xcode_project_pins_nexwit_development_team() -> None:
    content = _read(XCODE_PROJECT)

    assert content.count('DEVELOPMENT_TEAM = WH73RJDJXC;') >= 3
    assert 'DevelopmentTeam = WH73RJDJXC;' in content
    assert 'ProvisioningStyle = Automatic;' in content


def test_xcode_release_uses_tarot_app_store_profile() -> None:
    content = _read(XCODE_PROJECT)

    assert content.count('CODE_SIGN_IDENTITY = "Apple Distribution";') >= 2
    assert content.count('CODE_SIGN_STYLE = Manual;') >= 2
    assert (
        content.count(
            'PROVISIONING_PROFILE_SPECIFIER = "Tarot Reader AI App Store 2026";'
        )
        >= 2
    )


def test_ios_declares_no_nonexempt_encryption() -> None:
    content = _read(IOS_INFO_PLIST)

    assert '<key>ITSAppUsesNonExemptEncryption</key>' in content
    assert '<false/>' in content


def test_ios_launch_screen_uses_tarot_branding_not_flutter_placeholder() -> None:
    content = _read(LAUNCH_SCREEN)

    assert 'Tarot Reader AI' in content
    assert 'Insight in every card' in content
    assert 'image="LaunchImage"' not in content


def test_runbook_documents_exact_mac_and_testflight_flow() -> None:
    content = _read(RUNBOOK)

    for expected in (
        './scripts/macos/bootstrap_ios.sh',
        './scripts/macos/build_testflight.sh --build-name 1.0.0 --build-number 17',
        'APPLE_BACKEND_BASE_URL',
        'APPLE_PRIVACY_POLICY_URL',
        'Runner.xcworkspace',
        'Xcode Organizer',
        'Transporter',
        'TestFlight',
        'weekly_readings',
        'monthly_readings',
        'one10_readings',
        'one40_readings',
    ):
        assert expected in content

    assert 'signed IPA' in content
    assert 'Sandbox' in content
    assert 'Podfile.lock' in content
    assert 'codesign --verify --deep --strict' in content
    assert 'проверяет только' in content
    assert 'Python 3.11' in content


def _bash_executable() -> str:
    if sys.platform == 'darwin':
        bash = shutil.which('bash')
        assert bash is not None, 'bash must be available through PATH on macOS'
        return bash
    if sys.platform == 'win32':
        for candidate in (
            Path(r'C:\Program Files\Git\bin\bash.exe'),
            Path(r'C:\Program Files\Git\usr\bin\bash.exe'),
        ):
            if candidate.exists():
                return str(candidate)
        pytest.fail('Git Bash is required on Windows for bash -n checks')
    bash = shutil.which('bash')
    assert bash is not None, 'bash is required for bash -n checks'
    return bash


def test_shell_scripts_parse_when_git_bash_is_available() -> None:
    bash = _bash_executable()

    for script in (BOOTSTRAP, BUILD):
        script_relative = script.relative_to(REPO_ROOT).as_posix()
        result = subprocess.run(
            [bash, '-n', script_relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
