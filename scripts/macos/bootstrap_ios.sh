#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_BRANCH="codex/apple-app-store"
readonly MINIMUM_XCODE_MAJOR=26
readonly MINIMUM_IOS_SDK_MAJOR=26

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/../.." && pwd -P)"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local command_name="$1"
  local install_hint="$2"
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required. $install_hint"
}

version_major() {
  local version="$1"
  printf '%s\n' "${version%%.*}"
}

[[ "$(uname -s)" == "Darwin" ]] || fail "This script must run on macOS. Connect to the rented Mac and run it there."

require_command git "Install Xcode Command Line Tools with: xcode-select --install"
require_command xcodebuild "Install Xcode from the App Store and select it with xcode-select."
require_command xcrun "Install Xcode Command Line Tools with: xcode-select --install"
require_command flutter "Install stable Flutter and add it to PATH."
require_command pod "Install CocoaPods, for example: sudo gem install cocoapods"
require_command python3 "Install Python 3 and add it to PATH."
python3 "$script_dir/release_runtime_check.py"

verify_flutter_stable() {
  local version_json channel
  version_json="$(flutter --version --machine)"
  channel="$(python3 - "$version_json" <<'PY'
import json
import sys

channel = json.loads(sys.argv[1]).get('channel')
if channel != 'stable':
    raise SystemExit(f"ERROR: Flutter stable channel is required; found {channel or 'unknown'}.")
print(channel)
PY
)"
  [[ "$channel" == "stable" ]] || fail "Flutter stable channel is required; found $channel."
}

printf '== macOS ==\n'
sw_vers

printf '\n== Xcode ==\n'
xcode_version_output="$(xcodebuild -version)"
printf '%s\n' "$xcode_version_output"
xcode_version="$(printf '%s\n' "$xcode_version_output" | awk '/^Xcode / {print $2; exit}')"
[[ -n "$xcode_version" ]] || fail "Could not determine the Xcode version. Run: sudo xcode-select -s /Applications/Xcode.app"
[[ "$(version_major "$xcode_version")" =~ ^[0-9]+$ ]] || fail "Unexpected Xcode version: $xcode_version"
(( $(version_major "$xcode_version") >= MINIMUM_XCODE_MAJOR )) || fail "Xcode $MINIMUM_XCODE_MAJOR or newer is required; found $xcode_version."

printf '\n== iPhoneOS SDK ==\n'
ios_sdk_version="$(xcrun --sdk iphoneos --show-sdk-version)"
printf '%s\n' "$ios_sdk_version"
[[ "$(version_major "$ios_sdk_version")" =~ ^[0-9]+$ ]] || fail "Unexpected iPhoneOS SDK version: $ios_sdk_version"
(( $(version_major "$ios_sdk_version") >= MINIMUM_IOS_SDK_MAJOR )) || fail "iOS SDK $MINIMUM_IOS_SDK_MAJOR or newer is required; found $ios_sdk_version."

printf '\n== Flutter ==\n'
flutter --version
verify_flutter_stable
printf '\n== CocoaPods ==\n'
pod --version
printf '\n== Python ==\n'
python3 --version

git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$repo_root is not a Git checkout."
current_branch="$(git -C "$repo_root" branch --show-current)"
if [[ "$current_branch" != "$EXPECTED_BRANCH" ]]; then
  if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
    fail "The checkout is on '$current_branch' and has local changes. Preserve or commit them before switching to '$EXPECTED_BRANCH'. No files were changed."
  fi
  printf '\nSwitching clean checkout from %s to %s...\n' "$current_branch" "$EXPECTED_BRANCH"
  git -C "$repo_root" checkout "$EXPECTED_BRANCH"
else
  printf '\nBranch %s is active. Existing local changes will not be reset or cleaned.\n' "$EXPECTED_BRANCH"
fi

printf '\n== Flutter dependencies ==\n'
(
  cd "$repo_root/app"
  flutter pub get
)

printf '\n== CocoaPods dependencies ==\n'
lock_path="app/ios/Podfile.lock"
if git -C "$repo_root" ls-files --error-unmatch "$lock_path" >/dev/null 2>&1; then
  (
    cd "$repo_root/app/ios"
    pod install --deployment
  )
else
  (
    cd "$repo_root/app/ios"
    pod install
  )
  [[ -f "$repo_root/$lock_path" ]] || fail "pod install did not create $lock_path."
  fail "$lock_path was created by CocoaPods and must be reviewed and committed on the Mac. Commit it, then rerun bootstrap; the release build will never invent or ignore this lock."
fi

[[ -z "$(git -C "$repo_root" status --porcelain -- "$lock_path")" ]] || fail "$lock_path changed during pod install --deployment. Commit the intended lock update before continuing."

[[ -d "$repo_root/app/ios/Runner.xcworkspace" ]] || fail "CocoaPods did not create app/ios/Runner.xcworkspace. Review the pod install output."

printf '\n== Flutter analyze ==\n'
(
  cd "$repo_root/app"
  flutter analyze
)

printf '\n== Flutter tests ==\n'
(
  cd "$repo_root/app"
  flutter test
)

printf '\n== Backend tests ==\n'
(
  cd "$repo_root"
  python3 -m pytest backend/tests -q
)

printf '\nBootstrap complete. Open app/ios/Runner.xcworkspace in Xcode, select the Apple Developer Team for Runner, and confirm Bundle ID com.nexwit.tarot.\n'
