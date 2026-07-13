from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable


EXPECTED_PACKAGE = 'com.nexwit.tarot'
EXPECTED_BACKEND_URL = 'http://185.171.83.116:8022'
EXPECTED_BACKEND_SERVICE = 'PMapptaro Backend'
CURRENT_REMOTE_ENV = '/root/PMapptaro/.env'


@dataclasses.dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {'name': self.name, 'ok': self.ok, 'detail': self.detail}


def collect_local_checks(root: Path) -> list[CheckResult]:
    app_dir = root / 'app'
    pubspec = app_dir / 'pubspec.yaml'
    gradle = app_dir / 'android' / 'app' / 'build.gradle.kts'
    config = app_dir / 'lib' / 'core' / 'config' / 'app_config.dart'
    aab = app_dir / 'build' / 'app' / 'outputs' / 'bundle' / 'release' / 'app-release.aab'
    apk = app_dir / 'build' / 'app' / 'outputs' / 'flutter-apk' / 'app-release.apk'

    version = _first_match(pubspec, r'^version:\s*(\S+)', flags=re.MULTILINE)
    namespace = _first_match(gradle, r'namespace\s*=\s*"([^"]+)"')
    application_id = _first_match(gradle, r'applicationId\s*=\s*"([^"]+)"')
    backend_url = _first_match(config, r"fixedBackendBaseUrl\s*=\s*'([^']+)'")
    config_package = _first_match(config, r"androidPackageName\s*=\s*'([^']+)'")

    return [
        CheckResult(
            name='version',
            ok=bool(version),
            detail=version or f'missing version in {pubspec}',
        ),
        CheckResult(
            name='android package',
            ok=namespace == EXPECTED_PACKAGE
            and application_id == EXPECTED_PACKAGE
            and config_package == EXPECTED_PACKAGE,
            detail=(
                f'namespace={namespace or "missing"}, '
                f'applicationId={application_id or "missing"}, '
                f'config={config_package or "missing"}'
            ),
        ),
        CheckResult(
            name='backend URL',
            ok=backend_url == EXPECTED_BACKEND_URL,
            detail=backend_url or f'missing fixedBackendBaseUrl in {config}',
        ),
        CheckResult(
            name='release AAB artifact',
            ok=aab.is_file() and aab.stat().st_size > 0,
            detail=_artifact_detail(aab),
        ),
        CheckResult(
            name='release APK artifact',
            ok=apk.is_file() and apk.stat().st_size > 0,
            detail=_artifact_detail(apk),
        ),
    ]


def collect_remote_checks(
    *,
    host: str,
    user: str,
    password: str | None,
    port: int,
    key_filename: str | None,
) -> list[CheckResult]:
    try:
        import paramiko
    except ImportError as exc:
        return [
            CheckResult(
                name='remote dependency',
                ok=False,
                detail=f'paramiko is required for remote checks: {exc}',
            )
        ]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=user,
        password=password,
        key_filename=key_filename,
        port=port,
        timeout=20,
    )
    try:
        return _remote_checks_from_client(client)
    finally:
        client.close()


def _remote_checks_from_client(client) -> list[CheckResult]:
    checks: list[CheckResult] = []
    facts = _remote_fact_lines(
        client,
        r'''
test -d /root/PMapptaro && echo PMapptaro_DIR=present || echo PMapptaro_DIR=missing
test -f /root/PMapptaro/data/pmapptaro.db && echo PMapptaro_DB=present || echo PMapptaro_DB=missing
test -f /root/PMapptaro/data/google-play-service-account.json && echo GP_SERVICE_ACCOUNT=present || echo GP_SERVICE_ACCOUNT=missing
docker ps -a --filter name=pmapptaro --format 'CONTAINER {{.Names}}|{{.Status}}|{{.Ports}}'
python3 - <<'PY'
from pathlib import Path
import hashlib
for p in Path('/root').glob('*/.env'):
    token = ''
    try:
        for line in p.read_text(errors='ignore').splitlines():
            if line.startswith('ADMIN_BOT_TOKEN='):
                token = line.split('=', 1)[1].strip().strip('"\'')
                break
    except Exception:
        continue
    if token:
        print(f'ADMIN_TOKEN_HASH {p} {hashlib.sha256(token.encode()).hexdigest()[:12]}')
PY
''',
    )

    facts_text = '\n'.join(facts)
    checks.append(_presence_check('remote directory', 'PMapptaro_DIR=present', facts_text))
    checks.append(_presence_check('remote SQLite DB', 'PMapptaro_DB=present', facts_text))
    checks.append(_presence_check('Google Play service account', 'GP_SERVICE_ACCOUNT=present', facts_text))

    backend_line = _line_starting(facts, 'CONTAINER pmapptaro_backend|')
    admin_line = _line_starting(facts, 'CONTAINER pmapptaro_admin_bot|')
    checks.append(
        CheckResult(
            name='remote backend container',
            ok=backend_line is not None and '|Up ' in backend_line and ':8022->8000/tcp' in backend_line,
            detail=backend_line or 'pmapptaro_backend missing',
        )
    )
    checks.append(
        CheckResult(
            name='remote admin bot container',
            ok=admin_line is not None and '|Up ' in admin_line,
            detail=admin_line or 'pmapptaro_admin_bot missing',
        )
    )

    token_hashes = _admin_token_hashes(facts)
    duplicates = duplicate_admin_token_paths(token_hashes, current_project_env=CURRENT_REMOTE_ENV)
    checks.append(
        CheckResult(
            name='remote admin bot token uniqueness',
            ok=not duplicates,
            detail='unique' if not duplicates else f'duplicate token also used by: {", ".join(duplicates)}',
        )
    )
    return checks


def collect_backend_health_check(
    base_url: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> CheckResult:
    url = f'{base_url.rstrip("/")}/v1/health'
    fetch = fetch_json or _fetch_json
    try:
        payload = fetch(url)
    except Exception as exc:  # noqa: BLE001 - readiness output should include the operational error.
        return CheckResult(
            name='public backend health',
            ok=False,
            detail=f'{url} failed: {exc}',
        )

    status = str(payload.get('status', ''))
    service = str(payload.get('service', ''))
    ok = status == 'ok' and service == EXPECTED_BACKEND_SERVICE
    return CheckResult(
        name='public backend health',
        ok=ok,
        detail=f'{url} status={status or "missing"} service={service or "missing"}',
    )


def duplicate_admin_token_paths(
    token_hashes_by_path: dict[str, str],
    *,
    current_project_env: str,
) -> list[str]:
    current_hash = token_hashes_by_path.get(current_project_env)
    if not current_hash:
        return []
    return sorted(
        path
        for path, token_hash in token_hashes_by_path.items()
        if path != current_project_env and token_hash == current_hash
    )


def overall_exit_code(checks: Iterable[CheckResult]) -> int:
    return 0 if all(check.ok for check in checks) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check PMapptaro Google Play release readiness.')
    parser.add_argument('--repo-root', default='.', help='Repository root. Defaults to current directory.')
    parser.add_argument('--local-only', action='store_true', help='Skip SSH remote checks.')
    parser.add_argument('--skip-backend-health', action='store_true', help='Skip public /v1/health HTTP check.')
    parser.add_argument('--json', action='store_true', help='Print JSON instead of text.')
    parser.add_argument('--remote-host', default=os.getenv('PMAPPTARO_REMOTE_HOST', ''))
    parser.add_argument('--remote-user', default=os.getenv('PMAPPTARO_REMOTE_USER', 'root'))
    parser.add_argument('--remote-password', default=os.getenv('PMAPPTARO_REMOTE_PASSWORD'))
    parser.add_argument('--remote-key', default=os.getenv('PMAPPTARO_REMOTE_KEY'))
    parser.add_argument('--remote-port', default=int(os.getenv('PMAPPTARO_REMOTE_PORT', '22')), type=int)
    args = parser.parse_args(argv)

    root = Path(args.repo_root).resolve()
    checks = collect_local_checks(root)
    if not args.skip_backend_health:
        checks.append(collect_backend_health_check(EXPECTED_BACKEND_URL))

    if not args.local_only:
        if not args.remote_host:
            checks.append(
                CheckResult(
                    name='remote check configuration',
                    ok=False,
                    detail='pass --remote-host or set PMAPPTARO_REMOTE_HOST, or use --local-only',
                )
            )
        else:
            checks.extend(
                collect_remote_checks(
                    host=args.remote_host,
                    user=args.remote_user,
                    password=args.remote_password,
                    port=args.remote_port,
                    key_filename=args.remote_key,
                )
            )

    if args.json:
        print(json.dumps([check.as_dict() for check in checks], ensure_ascii=False, indent=2))
    else:
        for check in checks:
            mark = 'OK' if check.ok else 'FAIL'
            print(f'[{mark}] {check.name}: {check.detail}')
    return overall_exit_code(checks)


def _first_match(path: Path, pattern: str, *, flags: int = 0) -> str | None:
    if not path.is_file():
        return None
    match = re.search(pattern, path.read_text(encoding='utf-8'), flags)
    return match.group(1) if match else None


def _artifact_detail(path: Path) -> str:
    if not path.is_file():
        return f'missing {path}'
    return f'{path} ({path.stat().st_size} bytes)'


def _remote_fact_lines(client, command: str) -> list[str]:
    _stdin, stdout, stderr = client.exec_command(command, timeout=30)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace').strip()
    if err:
        raise RuntimeError(err)
    return [line.strip() for line in out.splitlines() if line.strip()]


def _fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - fixed operational endpoint.
        payload = response.read().decode('utf-8')
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError('health endpoint returned non-object JSON')
    return data


def _presence_check(name: str, marker: str, facts_text: str) -> CheckResult:
    return CheckResult(name=name, ok=marker in facts_text, detail='present' if marker in facts_text else 'missing')


def _line_starting(lines: Iterable[str], prefix: str) -> str | None:
    return next((line for line in lines if line.startswith(prefix)), None)


def _admin_token_hashes(lines: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        if not line.startswith('ADMIN_TOKEN_HASH '):
            continue
        _prefix, path, token_hash = line.split(maxsplit=2)
        result[path] = token_hash
    return result


if __name__ == '__main__':
    raise SystemExit(main())
