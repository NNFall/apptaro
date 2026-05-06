Param(
    [switch]$Release = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
$appDir = Join-Path $repoRoot "app"

Push-Location $appDir
try {
    if ($Release) {
        flutter build apk --release
    }
    else {
        flutter build apk
    }

    $pubspec = Get-Content -Path (Join-Path $appDir "pubspec.yaml") -Raw
    $versionMatch = [regex]::Match($pubspec, "version:\s*([0-9]+\.[0-9]+\.[0-9]+)\+([0-9]+)")
    if (-not $versionMatch.Success) {
        throw "Cannot parse version from pubspec.yaml"
    }

    $versionName = $versionMatch.Groups[1].Value
    $versionCode = $versionMatch.Groups[2].Value
    $apkDir = Join-Path $appDir "build\\app\\outputs\\flutter-apk"
    $sourceApk = Join-Path $apkDir "app-release.apk"
    if (-not (Test-Path $sourceApk)) {
        $sourceApk = Join-Path $apkDir "app-debug.apk"
    }
    if (-not (Test-Path $sourceApk)) {
        throw "APK not found in $apkDir"
    }

    $versionedApk = Join-Path $apkDir ("apptaro-v{0}+{1}.apk" -f $versionName, $versionCode)
    $stableApk = Join-Path $apkDir "apptaro.apk"
    Copy-Item -Path $sourceApk -Destination $versionedApk -Force
    Copy-Item -Path $sourceApk -Destination $stableApk -Force

    Write-Host "Created:"
    Write-Host " - $stableApk"
    Write-Host " - $versionedApk"
}
finally {
    Pop-Location
}
