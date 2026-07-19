#!/usr/bin/env bash
set -euo pipefail

# CocoaPods can inherit ASCII-8BIT in non-interactive SSH sessions and fail
# while normalizing the project path. Keep release tooling explicitly UTF-8.
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

readonly EXPECTED_BRANCH="codex/apple-app-store"
readonly EXPECTED_BUNDLE_ID="com.nexwit.tarotreaderai"
readonly DEFAULT_PROBE_TIMEOUT_SECONDS=8

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/../.." && pwd -P)"
app_dir="$repo_root/app"
export_options_plist="$app_dir/ios/ExportOptions.plist"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./scripts/macos/build_testflight.sh --build-name X.Y.Z --build-number N

Required environment variables:
  APPLE_BACKEND_BASE_URL       Production HTTPS origin, without a path.
  APPLE_PRIVACY_POLICY_URL     Public absolute HTTPS privacy policy URL.

The build number must be greater than the build number in app/pubspec.yaml.
Configure the Apple Developer Team for Runner in app/ios/Runner.xcworkspace first.
EOF
}

build_name=''
build_number=''
while (($# > 0)); do
  case "$1" in
    --build-name)
      (($# >= 2)) || fail "--build-name requires a value."
      build_name="$2"
      shift 2
      ;;
    --build-number)
      (($# >= 2)) || fail "--build-number requires a value."
      build_number="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ "$(uname -s)" == "Darwin" ]] || fail "This script must run on macOS."
[[ -n "$build_name" ]] || { usage >&2; fail "--build-name is required."; }
[[ -n "$build_number" ]] || { usage >&2; fail "--build-number is required."; }
[[ "$build_name" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || fail "--build-name must be a release version such as 1.0.0."
[[ "$build_number" =~ ^[1-9][0-9]*$ ]] || fail "--build-number must be a positive integer without leading zeroes."

: "${APPLE_BACKEND_BASE_URL:?APPLE_BACKEND_BASE_URL is required. Use a production https:// origin.}"
: "${APPLE_PRIVACY_POLICY_URL:?APPLE_PRIVACY_POLICY_URL is required. Use a public https:// URL.}"

for command_name in git flutter pod python3 xcodebuild unzip find shasum codesign security; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required. Run ./scripts/macos/bootstrap_ios.sh first."
done
python3 "$script_dir/release_runtime_check.py"
[[ -x /usr/libexec/PlistBuddy ]] || fail "/usr/libexec/PlistBuddy is required to verify the IPA metadata."
[[ -f "$export_options_plist" ]] || fail "Missing iOS export options: $export_options_plist"

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

verify_flutter_stable

current_branch="$(git -C "$repo_root" branch --show-current)"
[[ "$current_branch" == "$EXPECTED_BRANCH" ]] || fail "Expected branch '$EXPECTED_BRANCH', found '$current_branch'."

dirty_app="$(git -C "$repo_root" status --porcelain -- app)"
[[ -z "$dirty_app" ]] || fail "The app directory has uncommitted files. Commit or preserve them before creating a release IPA:\n$dirty_app"

lock_path="app/ios/Podfile.lock"
git -C "$repo_root" ls-files --error-unmatch "$lock_path" >/dev/null 2>&1 || fail "$lock_path must be generated on the Mac, reviewed, and committed before a release build. Run bootstrap first; do not fabricate the lock on Windows."
[[ -f "$repo_root/$lock_path" ]] || fail "Tracked $lock_path is missing from the working tree."
[[ -z "$(git -C "$repo_root" status --porcelain -- "$lock_path")" ]] || fail "$lock_path has uncommitted changes. Commit the intended dependency lock before building."

project_file="$app_dir/ios/Runner.xcodeproj/project.pbxproj"
[[ -f "$project_file" ]] || fail "Missing $project_file."
grep -Eq "PRODUCT_BUNDLE_IDENTIFIER = ${EXPECTED_BUNDLE_ID//./\\.};" "$project_file" || fail "Runner Bundle ID must be $EXPECTED_BUNDLE_ID."

pubspec="$app_dir/pubspec.yaml"
current_build_number="$(sed -nE 's/^[[:space:]]*version:[[:space:]]*[^+]+\+([0-9]+)[[:space:]]*$/\1/p' "$pubspec" | head -n 1)"
[[ "$current_build_number" =~ ^[0-9]+$ ]] || fail "Could not read the current build number from app/pubspec.yaml."
(( build_number > current_build_number )) || fail "Build number $build_number must be greater than app/pubspec.yaml build $current_build_number. This local check cannot verify uniqueness in App Store Connect; duplicate uploaded numbers are rejected during upload."

probe_timeout_seconds="${RELEASE_PROBE_TIMEOUT_SECONDS:-$DEFAULT_PROBE_TIMEOUT_SECONDS}"
python3 "$script_dir/release_url_probe.py" \
  --backend-origin "$APPLE_BACKEND_BASE_URL" \
  --privacy-url "$APPLE_PRIVACY_POLICY_URL" \
  --timeout-seconds "$probe_timeout_seconds"

printf 'Cleaning generated Flutter output and restoring dependencies...\n'
(
  cd "$app_dir"
  flutter clean
  flutter pub get
)
(
  cd "$app_dir/ios"
  pod install --deployment
)
[[ -d "$app_dir/ios/Runner.xcworkspace" ]] || fail "Missing Runner.xcworkspace after pod install."

dependency_dirty_app="$(git -C "$repo_root" status --porcelain -- app)"
[[ -z "$dependency_dirty_app" ]] || fail "Dependency resolution changed files inside app/. Review and commit the dependency changes before building:\n$dependency_dirty_app"

if ! signing_settings="$(
  cd "$app_dir/ios"
  xcodebuild -workspace Runner.xcworkspace -scheme Runner -configuration Release -showBuildSettings 2>/dev/null
)"; then
  fail "Xcode could not read Release signing settings. Open app/ios/Runner.xcworkspace, resolve signing errors, then retry."
fi
development_team="$(printf '%s\n' "$signing_settings" | sed -nE 's/^[[:space:]]*DEVELOPMENT_TEAM = ([A-Za-z0-9]+)[[:space:]]*$/\1/p' | head -n 1)"
[[ -n "$development_team" ]] || fail "No Apple Development Team is configured. Open app/ios/Runner.xcworkspace in Xcode, select Runner > Signing & Capabilities, choose the team, then retry."

python3 "$repo_root/scripts/check_ios_distribution.py" \
  --repo-root "$repo_root" \
  --apple-backend-base-url "$APPLE_BACKEND_BASE_URL" \
  --apple-privacy-policy-url "$APPLE_PRIVACY_POLICY_URL"

printf 'Building signed App Store IPA for team %s...\n' "$development_team"
(
  cd "$app_dir"
  flutter build ipa --release \
    --build-name "$build_name" \
    --build-number "$build_number" \
    --export-options-plist "$export_options_plist" \
    --dart-define=APPLE_BACKEND_BASE_URL="$APPLE_BACKEND_BASE_URL" \
    --dart-define=APPLE_PRIVACY_POLICY_URL="$APPLE_PRIVACY_POLICY_URL"
)

ipa_files=()
while IFS= read -r -d '' candidate; do
  ipa_files[${#ipa_files[@]}]="$candidate"
done < <(find "$app_dir/build/ios/ipa" -maxdepth 1 -type f -name '*.ipa' -size +0c -print0)
(( ${#ipa_files[@]} == 1 )) || fail "Expected exactly one non-empty IPA in app/build/ios/ipa; found ${#ipa_files[@]}."
ipa_path="${ipa_files[0]}"

verify_dir="$(mktemp -d)"
trap 'rm -rf "$verify_dir"' EXIT
unzip -q "$ipa_path" -d "$verify_dir"
app_plists=()
while IFS= read -r -d '' candidate; do
  app_plists[${#app_plists[@]}]="$candidate"
done < <(find "$verify_dir/Payload" -mindepth 2 -maxdepth 2 -type f -name Info.plist -print0)
(( ${#app_plists[@]} == 1 )) || fail "Expected one Payload/*.app/Info.plist in the IPA; found ${#app_plists[@]}."
app_plist="${app_plists[0]}"
app_bundle="$(dirname "$app_plist")"

actual_bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app_plist")"
actual_build_name="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app_plist")"
actual_build_number="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$app_plist")"
[[ "$actual_bundle_id" == "$EXPECTED_BUNDLE_ID" ]] || fail "IPA Bundle ID is '$actual_bundle_id', expected '$EXPECTED_BUNDLE_ID'."
[[ "$actual_build_name" == "$build_name" ]] || fail "IPA version is '$actual_build_name', expected '$build_name'."
[[ "$actual_build_number" == "$build_number" ]] || fail "IPA build number is '$actual_build_number', expected '$build_number'."

codesign --verify --deep --strict --verbose=2 "$app_bundle"
profile_path="$app_bundle/embedded.mobileprovision"
[[ -f "$profile_path" ]] || fail "Signed IPA does not contain embedded.mobileprovision."
profile_plist="$verify_dir/embedded-profile.plist"
security cms -D -i "$profile_path" > "$profile_plist" || fail "security cms could not decode embedded.mobileprovision."
app_entitlements="$verify_dir/app-entitlements.plist"
codesign -d --entitlements :- "$app_bundle" > "$app_entitlements" 2>/dev/null || fail "codesign could not read application entitlements."

python3 "$script_dir/release_profile_validator.py" \
  --profile-plist "$profile_plist" \
  --app-entitlements-plist "$app_entitlements" \
  --expected-team "$development_team" \
  --expected-bundle "$EXPECTED_BUNDLE_ID"

printf '\nIPA signature and App Store distribution profile verified successfully:\n'
printf '  Path: %s\n' "$ipa_path"
printf '  Bundle ID: %s\n' "$actual_bundle_id"
printf '  Version: %s (%s)\n' "$actual_build_name" "$actual_build_number"
printf '  SHA-256: '
shasum -a 256 "$ipa_path" | awk '{print $1}'

cat <<EOF

Manual upload and TestFlight steps (credentials are intentionally not automated):
1. Open Xcode Organizer and upload the archive, or open Transporter and select:
   $ipa_path
2. In App Store Connect, wait until build $build_number finishes processing.
3. Attach all four in-app products to the version and enable the TestFlight group.
4. Install from TestFlight and collect Sandbox evidence for purchase, restore, renewal, refund, notifications, and admin-bot events.
EOF
