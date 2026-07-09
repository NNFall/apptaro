from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import time
from pathlib import Path

import paramiko

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - fallback for minimal environments
    dotenv_values = None


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / 'backend'
TEMPLATES_DIR = BACKEND_DIR / 'runtime' / 'templates'
TAROT_DIR = BACKEND_DIR / 'runtime' / 'tarot'
ADMIN_BOT_DIR = REPO_ROOT / 'telegram_admin_bot'
COMPOSE_FILE = REPO_ROOT / 'docker-compose.backend.yml'
BACKEND_SERVICE_NAME = 'pmapptaro_backend'
ADMIN_BOT_SERVICE_NAME = 'pmapptaro_admin_bot'
DEFAULT_REMOTE_DIR = '/root/PMapptaro'
DEFAULT_HOST_PORT = 8022
WATCHDOG_SCRIPT_NAME = 'pmapptaro_admin_bot_watchdog.sh'
WATCHDOG_CRON_NAME = 'pmapptaro_admin_bot_watchdog'
GOOGLE_PLAY_SERVICE_ACCOUNT_FILENAME = 'google-play-service-account.json'
EXPECTED_HEALTH_SERVICE = 'PMapptaro Backend'

BACKEND_SKIP_PARTS = {
    '.venv',
    '__pycache__',
    '.pytest_cache',
    'runtime',
    'data',
    '.mypy_cache',
}
BACKEND_SKIP_SUFFIXES = {'.pyc', '.pyo'}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Deploy PMapptaro Google Play backend to a remote Docker host.')
    parser.add_argument('--host', required=True)
    parser.add_argument('--user', default='root')
    parser.add_argument('--password', required=True)
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--remote-dir', default=DEFAULT_REMOTE_DIR)
    parser.add_argument(
        '--google-play-service-account-file',
        default='',
        help=(
            'Optional local Google Play service-account JSON file to upload to '
            f'<remote-dir>/data/{GOOGLE_PLAY_SERVICE_ACCOUNT_FILENAME}.'
        ),
    )
    parser.add_argument(
        '--backend-only',
        action='store_true',
        help=(
            'Deploy and restart only pmapptaro_backend. Use this while the Google Play '
            'admin bot does not have a unique Telegram token yet.'
        ),
    )
    return parser.parse_args()


def load_local_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (
        REPO_ROOT / '.env',
        BACKEND_DIR / '.env',
        REPO_ROOT / 'telegram_taro_bot' / '.env',
        ADMIN_BOT_DIR / '.env',
    ):
        if not path.exists():
            continue
        values = _read_env_file(path)
        for key, value in values.items():
            if value is not None:
                merged[key] = value
    return merged


def _read_env_file(path: Path) -> dict[str, str | None]:
    if dotenv_values is not None:
        return dict(dotenv_values(path))

    values: dict[str, str | None] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = _strip_env_value(value.strip())
    return values


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def build_remote_env(local_env: dict[str, str], host_port: int) -> str:
    google_play_service_account_file = local_env.get('GOOGLE_PLAY_SERVICE_ACCOUNT_FILE', '').strip()
    if not google_play_service_account_file.startswith('/'):
        google_play_service_account_file = '/data/google-play-service-account.json'

    env: dict[str, str] = {
        'APP_NAME': local_env.get('APP_NAME', 'PMapptaro Backend'),
        'APP_ENV': 'production',
        'APP_VERSION': local_env.get('APP_VERSION', '0.1.0'),
        'APP_HOST': '0.0.0.0',
        'APP_PORT': '8000',
        'HOST_PORT': str(host_port),
        'LOG_LEVEL': local_env.get('LOG_LEVEL', 'INFO'),
        'CORS_ALLOW_ORIGINS': local_env.get('CORS_ALLOW_ORIGINS', '*'),
        'LIBREOFFICE_PATH': 'soffice',
        'FONT_FALLBACK': 'Carlito',
        'FONT_WHITELIST': local_env.get('FONT_WHITELIST', 'Cambria,Calibri,Arial,Times New Roman'),
        'FONTS_DIR': '/usr/share/fonts',
        'DATA_DIR': '/data',
        'DATABASE_PATH': '/data/pmapptaro.db',
        'TEMP_DIR': '/app/runtime/temp',
        'TEMPLATES_DIR': '/app/runtime/templates',
        'TAROT_CARDS_DIR': '/app/runtime/tarot/cards',
        'TAROT_BACKGROUND_PATH': '/app/runtime/tarot/backgrounds/main.png',
        'TAROT_LAYOUT_PATH': '/app/runtime/tarot/layout.json',
        'GOOGLE_PLAY_PACKAGE_NAME': local_env.get('GOOGLE_PLAY_PACKAGE_NAME', 'com.apptaro.app'),
        'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE': google_play_service_account_file,
        'GOOGLE_PLAY_TEST_MODE': local_env.get('GOOGLE_PLAY_TEST_MODE', '0'),
        'IMAGE_CONCURRENCY': local_env.get('IMAGE_CONCURRENCY', '5'),
        'IMAGE_GENERATION_RETRIES': local_env.get('IMAGE_GENERATION_RETRIES', '2'),
        'IMAGE_GENERATION_RETRY_DELAY_SECONDS': local_env.get('IMAGE_GENERATION_RETRY_DELAY_SECONDS', '2.0'),
        'YOOKASSA_RETURN_URL': local_env.get('YOOKASSA_RETURN_URL', 'apptaro://billing/return'),
        'ENABLE_LEGACY_YOOKASSA_BILLING': local_env.get('ENABLE_LEGACY_YOOKASSA_BILLING', '0'),
        'OFFER_URL': local_env.get('GOOGLE_PLAY_OFFER_URL', '').strip(),
        'SUPPORT_MAX_URL': local_env.get(
            'SUPPORT_MAX_URL',
            'https://max.ru/u/f9LHodD0cOL1NLfuFBoMvvVMSgRmsLKspQSSM1d9_6ZR68W1oT3zfN20xA8',
        ),
        'ADMIN_BOT_HEARTBEAT_PATH': local_env.get('ADMIN_BOT_HEARTBEAT_PATH', '/tmp/admin_bot.heartbeat'),
        'ADMIN_BOT_POLLING_TIMEOUT_SECONDS': local_env.get('ADMIN_BOT_POLLING_TIMEOUT_SECONDS', '50'),
        'ADMIN_BOT_POLLING_RETRY_MAX_SECONDS': local_env.get('ADMIN_BOT_POLLING_RETRY_MAX_SECONDS', '30'),
        'ADMIN_BOT_WATCHDOG_MAX_AGE_SECONDS': local_env.get('ADMIN_BOT_WATCHDOG_MAX_AGE_SECONDS', '180'),
        'TZ': 'Europe/Samara',
    }

    passthrough_keys = (
        'KIE_API_KEY',
        'KIE_BASE_URL',
        'KIE_TEXT_MODEL',
        'KIE_TEXT_ENDPOINT',
        'KIE_TEXT_FALLBACK_MODELS',
        'KIE_IMAGE_MODEL',
        'KIE_IMAGE_ENDPOINT',
        'REPLICATE_API_TOKEN',
        'REPLICATE_BASE_URL',
        'REPLICATE_MODEL',
        'REPLICATE_DEFAULT_INPUT',
        'REPLICATE_TEXT_MODEL',
        'REPLICATE_TEXT_PROMPT_FIELD',
        'REPLICATE_WAIT_SECONDS',
        'REPLICATE_POLL_INTERVAL',
        'REPLICATE_TIMEOUT_SECONDS',
        'REPLICATE_TEXT_DEFAULT_INPUT',
        'YOOKASSA_SHOP_ID',
        'YOOKASSA_SECRET',
        'YOOKASSA_SECRET_KEY',
        'YOOKASSA_RETURN_URL',
        'YOOKASSA_RECEIPT_EMAIL',
        'YOOKASSA_RECEIPT_PHONE',
        'YOOKASSA_TAX_SYSTEM_CODE',
        'YOOKASSA_VAT_CODE',
        'YOOKASSA_ITEM_NAME',
        'YOOKASSA_PAYMENT_SUBJECT',
        'YOOKASSA_PAYMENT_MODE',
        'YOOKASSA_POLL_INTERVAL',
        'YOOKASSA_POLL_TIMEOUT',
        'YOOKASSA_TEST_MODE',
        'ENABLE_LEGACY_YOOKASSA_BILLING',
        'SUPPORT_USERNAME',
        'SUPPORT_MAX_URL',
        'AUTO_RENEW_INTERVAL',
        'ADMIN_BOT_TOKEN',
        'ADMIN_BOT_USERNAME',
        'ADMIN_IDS',
        'APP_SHARE_URL',
        'MAILER_TEMPLATE_INDEX',
        'ADMIN_BOT_HEARTBEAT_PATH',
        'ADMIN_BOT_POLLING_TIMEOUT_SECONDS',
        'ADMIN_BOT_POLLING_RETRY_MAX_SECONDS',
        'ADMIN_BOT_WATCHDOG_MAX_AGE_SECONDS',
        'GOOGLE_PLAY_PACKAGE_NAME',
        'GOOGLE_PLAY_SERVICE_ACCOUNT_JSON',
        'GOOGLE_PLAY_TEST_MODE',
    )
    for key in passthrough_keys:
        value = local_env.get(key)
        if value:
            env[key] = value

    return ''.join(f'{key}={_format_env_value(value)}\n' for key, value in env.items())


def _format_env_value(value: str) -> str:
    if value == '':
        return ''
    if any(ch.isspace() for ch in value) or any(ch in value for ch in '#"\'') or value[:1] in {'{', '['}:
        return json.dumps(value, ensure_ascii=False)
    return value


def _env_value(content: str, key: str) -> str:
    prefix = f'{key}='
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or not line.startswith(prefix):
            continue
        return _strip_env_value(line.split('=', 1)[1].strip())
    return ''


def resolve_google_play_service_account_file(
    local_env: dict[str, str],
    explicit_path: str = '',
) -> Path | None:
    if local_env.get('GOOGLE_PLAY_SERVICE_ACCOUNT_JSON', '').strip():
        return None

    has_explicit_path = bool(explicit_path.strip())
    raw_path = explicit_path.strip() or local_env.get('GOOGLE_PLAY_SERVICE_ACCOUNT_FILE', '').strip()
    if not raw_path:
        return None
    if not has_explicit_path and raw_path.startswith('/data/'):
        return None

    local_path = Path(raw_path).expanduser()
    if not local_path.is_absolute():
        local_path = (REPO_ROOT / local_path).resolve()

    if not local_path.exists():
        raise FileNotFoundError(f'Google Play service-account file was not found: {local_path}')
    if not local_path.is_file():
        raise FileNotFoundError(f'Google Play service-account path is not a file: {local_path}')

    with local_path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f'Google Play service-account file must contain a JSON object: {local_path}')
    return local_path


def ensure_remote_admin_bot_token_is_unique(
    remote: 'RemoteHost',
    remote_dir: str,
    remote_env: str,
) -> None:
    admin_token = _env_value(remote_env, 'ADMIN_BOT_TOKEN')
    if not admin_token:
        return

    token_hash = hashlib.sha256(admin_token.encode('utf-8')).hexdigest()
    remote_dir_norm = posixpath.normpath(remote_dir).rstrip('/')
    command = f"""
python3 - <<'PY'
from pathlib import Path
import hashlib

target_hash = {json.dumps(token_hash)}
current_dir = {json.dumps(remote_dir_norm)}
conflicts = []

for path in sorted(Path('/root').glob('*')):
    env_path = path / '.env'
    if not env_path.exists():
        continue
    env_dir = str(path)
    if env_dir == current_dir or env_dir.startswith(current_dir + '/'):
        continue
    token = ''
    for line in env_path.read_text(errors='ignore').splitlines():
        if line.startswith('ADMIN_BOT_TOKEN='):
            token = line.split('=', 1)[1].strip().strip('"\\'')
            break
    if token and hashlib.sha256(token.encode('utf-8')).hexdigest() == target_hash:
        conflicts.append(str(env_path))

if conflicts:
    print('\\n'.join(conflicts))
    raise SystemExit(2)
PY
"""
    exit_code, out, err = remote.run(command, check=False)
    if exit_code == 2:
        conflict_paths = ', '.join(item.strip() for item in out.splitlines() if item.strip())
        raise RuntimeError(
            'ADMIN_BOT_TOKEN is already used by another remote project: '
            f'{conflict_paths}. Create a separate Telegram admin bot token for PMapptaro '
            'or stop the old conflicting admin bot before deploying.'
        )
    if exit_code != 0:
        raise RuntimeError(f'Failed to check remote admin bot token uniqueness.\nSTDOUT:\n{out}\nSTDERR:\n{err}')


def ensure_admin_bot_token_is_configured(remote_env: str) -> None:
    if _env_value(remote_env, 'ADMIN_BOT_TOKEN'):
        return
    raise RuntimeError(
        'ADMIN_BOT_TOKEN is not configured for full PMapptaro deploy. '
        'Set a unique Telegram admin bot token or use --backend-only.'
    )


def upload_google_play_service_account(
    remote: 'RemoteHost',
    remote_dir: str,
    local_path: Path | None,
) -> None:
    if local_path is None:
        return
    remote_path = posixpath.join(remote_dir, 'data', GOOGLE_PLAY_SERVICE_ACCOUNT_FILENAME)
    remote.upload_file(local_path, remote_path)
    remote.run(f"chmod 600 '{remote_path}'")
    print(f'Uploaded Google Play service-account JSON to {remote_path}')


class RemoteHost:
    def __init__(self, host: str, user: str, password: str, port: int) -> None:
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(hostname=host, username=user, password=password, port=port, timeout=20)
        self._sftp = self._client.open_sftp()

    def close(self) -> None:
        self._sftp.close()
        self._client.close()

    def run(self, command: str, check: bool = True) -> tuple[int, str, str]:
        stdin, stdout, stderr = self._client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if check and exit_code != 0:
            raise RuntimeError(f'Command failed ({exit_code}): {command}\nSTDOUT:\n{out}\nSTDERR:\n{err}')
        return exit_code, out, err

    def ensure_dir(self, remote_dir: str) -> None:
        self.run(f"mkdir -p '{remote_dir}'")

    def remove_tree(self, remote_dir: str) -> None:
        self.run(f"rm -rf '{remote_dir}'")

    def upload_text(self, content: str, remote_path: str) -> None:
        parent = posixpath.dirname(remote_path)
        if parent:
            self.ensure_dir(parent)
        with self._sftp.file(remote_path, 'w') as remote_file:
            remote_file.write(content)

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        parent = posixpath.dirname(remote_path)
        if parent:
            self.ensure_dir(parent)
        self._sftp.put(str(local_path), remote_path)

    def upload_tree(self, local_root: Path, remote_root: str, skip_backend_filters: bool = False) -> None:
        for path in sorted(local_root.rglob('*')):
            relative = path.relative_to(local_root)
            if skip_backend_filters and _skip_backend_path(relative):
                continue
            remote_path = posixpath.join(remote_root, *relative.parts)
            if path.is_dir():
                self.ensure_dir(remote_path)
                continue
            self.upload_file(path, remote_path)


def _skip_backend_path(relative: Path) -> bool:
    if any(part in BACKEND_SKIP_PARTS for part in relative.parts):
        return True
    return relative.suffix.lower() in BACKEND_SKIP_SUFFIXES


def ensure_required_paths() -> None:
    for path in (BACKEND_DIR, ADMIN_BOT_DIR, TEMPLATES_DIR, TAROT_DIR, COMPOSE_FILE):
        if not path.exists():
            raise FileNotFoundError(f'Missing required path: {path}')


def ensure_remote_docker(remote: RemoteHost) -> None:
    remote.run("command -v curl >/dev/null 2>&1 || (apt-get update && apt-get install -y curl)")

    exit_code, _, _ = remote.run('docker --version >/dev/null 2>&1', check=False)
    if exit_code == 0:
        remote.run(
            "docker compose version >/dev/null 2>&1 || (apt-get update && apt-get install -y docker-compose-plugin)"
        )
        return

    remote.run('apt-get update && apt-get install -y ca-certificates curl')
    remote.run('curl -fsSL https://get.docker.com | sh')
    remote.run('apt-get update && apt-get install -y docker-compose-plugin')
    remote.run('systemctl enable --now docker')


def ensure_remote_cron(remote: RemoteHost) -> None:
    exit_code, _, _ = remote.run('command -v cron >/dev/null 2>&1', check=False)
    if exit_code != 0:
        remote.run('apt-get update && apt-get install -y cron')
    remote.run('systemctl enable --now cron')


def _watchdog_script(remote_dir: str, heartbeat_path: str, max_age_seconds: int) -> str:
    return f"""#!/bin/sh
set -eu

REMOTE_DIR="{remote_dir}"
CONTAINER_NAME="{ADMIN_BOT_SERVICE_NAME}"
HEARTBEAT_PATH="{heartbeat_path}"
MAX_AGE_SECONDS="{max_age_seconds}"

if ! docker ps --format '{{{{.Names}}}}' | grep -qx "$CONTAINER_NAME"; then
  exit 0
fi

AGE="$(docker exec "$CONTAINER_NAME" sh -lc '
if [ -f "$1" ]; then
  now=$(date +%s)
  hb=$(stat -c %Y "$1")
  echo $((now-hb))
else
  echo 999999
fi
' -- "$HEARTBEAT_PATH" 2>/dev/null || echo 999999)"

if [ "$AGE" -gt "$MAX_AGE_SECONDS" ]; then
  cd "$REMOTE_DIR"
  docker compose restart {ADMIN_BOT_SERVICE_NAME} >/dev/null 2>&1 || true
fi
"""


def install_admin_bot_watchdog(
    remote: RemoteHost,
    remote_dir: str,
    *,
    heartbeat_path: str,
    max_age_seconds: int,
) -> None:
    script_remote_path = posixpath.join(remote_dir, WATCHDOG_SCRIPT_NAME)
    cron_remote_path = f'/etc/cron.d/{WATCHDOG_CRON_NAME}'
    remote.upload_text(
        _watchdog_script(remote_dir, heartbeat_path, max_age_seconds),
        script_remote_path,
    )
    remote.run(f"chmod +x '{script_remote_path}'")
    cron_content = (
        f"*/2 * * * * root {script_remote_path} >> /var/log/{WATCHDOG_CRON_NAME}.log 2>&1\n"
    )
    remote.upload_text(cron_content, cron_remote_path)
    remote.run(f"chmod 644 '{cron_remote_path}'")
    remote.run('systemctl restart cron')


def deploy(
    remote: RemoteHost,
    remote_dir: str,
    remote_env: str,
    google_play_service_account_file: Path | None = None,
) -> None:
    backend_remote = posixpath.join(remote_dir, 'backend')
    admin_bot_remote = posixpath.join(remote_dir, 'telegram_admin_bot')
    templates_remote = posixpath.join(remote_dir, 'templates')
    tarot_remote = posixpath.join(remote_dir, 'tarot')
    remote.ensure_dir(remote_dir)
    for name in ('data', 'temp', 'logs', 'templates', 'tarot'):
        remote.ensure_dir(posixpath.join(remote_dir, name))

    upload_google_play_service_account(remote, remote_dir, google_play_service_account_file)

    for path in (backend_remote, admin_bot_remote, templates_remote, tarot_remote):
        remote.remove_tree(path)

    remote.upload_tree(BACKEND_DIR, backend_remote, skip_backend_filters=True)
    remote.upload_tree(ADMIN_BOT_DIR, admin_bot_remote)
    remote.ensure_dir(templates_remote)
    remote.upload_tree(TEMPLATES_DIR, templates_remote)
    remote.upload_tree(TAROT_DIR, tarot_remote)
    remote.upload_file(COMPOSE_FILE, posixpath.join(remote_dir, 'docker-compose.yml'))
    remote.upload_text(remote_env, posixpath.join(remote_dir, '.env'))

    remote.run(f"cd '{remote_dir}' && docker compose down --remove-orphans", check=False)
    remote.run(f"cd '{remote_dir}' && docker compose up -d --build --remove-orphans")


def deploy_backend_only(
    remote: RemoteHost,
    remote_dir: str,
    remote_env: str,
    google_play_service_account_file: Path | None = None,
) -> None:
    backend_remote = posixpath.join(remote_dir, 'backend')
    templates_remote = posixpath.join(remote_dir, 'templates')
    tarot_remote = posixpath.join(remote_dir, 'tarot')
    remote.ensure_dir(remote_dir)
    for name in ('data', 'temp', 'logs', 'templates', 'tarot'):
        remote.ensure_dir(posixpath.join(remote_dir, name))

    upload_google_play_service_account(remote, remote_dir, google_play_service_account_file)

    for path in (backend_remote, templates_remote, tarot_remote):
        remote.remove_tree(path)

    remote.upload_tree(BACKEND_DIR, backend_remote, skip_backend_filters=True)
    remote.ensure_dir(templates_remote)
    remote.upload_tree(TEMPLATES_DIR, templates_remote)
    remote.upload_tree(TAROT_DIR, tarot_remote)
    remote.upload_file(COMPOSE_FILE, posixpath.join(remote_dir, 'docker-compose.yml'))
    remote.upload_text(remote_env, posixpath.join(remote_dir, '.env'))

    remote.run(f"cd '{remote_dir}' && docker compose up -d --build {BACKEND_SERVICE_NAME}")


def wait_for_health(remote: RemoteHost, remote_dir: str, host_port: int, timeout_seconds: int = 180) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        exit_code, out, _ = remote.run(
            f"curl -fsS --max-time 5 http://127.0.0.1:{host_port}/v1/health",
            check=False,
        )
        if exit_code == 0 and is_expected_health_response(out):
            return out.strip()
        time.sleep(3)

    _, logs_out, logs_err = remote.run(
        f"cd '{remote_dir}' && docker compose logs --tail=200",
        check=False,
    )
    raise RuntimeError(f'Health check did not pass in time.\nLOGS:\n{logs_out}\n{logs_err}')


def is_expected_health_response(raw: str) -> bool:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return (
        payload.get('status') == 'ok'
        and payload.get('service') == EXPECTED_HEALTH_SERVICE
    )


def choose_host_port(remote: RemoteHost, preferred_port: int = DEFAULT_HOST_PORT) -> int:
    exit_code, out, _ = remote.run(
        f"ss -ltn '( sport = :{preferred_port} )' | sed -n '2,$p'",
        check=False,
    )
    if exit_code == 0 and not out.strip():
        return preferred_port

    exit_code, container_out, _ = remote.run(
        f"docker ps --format '{{{{.Names}}}} {{{{.Ports}}}}' | grep -E '^({BACKEND_SERVICE_NAME}) '",
        check=False,
    )
    if exit_code == 0 and f':{preferred_port}->' in container_out:
        return preferred_port

    raise RuntimeError(
        f'Host port {preferred_port} is busy. PMapptaro Google Play client is fixed to this port, '
        'so release the port or update the application configuration before redeploy.'
    )


def main() -> int:
    args = parse_args()
    ensure_required_paths()
    local_env = load_local_env()
    google_play_service_account_file = resolve_google_play_service_account_file(
        local_env,
        args.google_play_service_account_file,
    )

    print(f'Deploying backend to {args.user}@{args.host}:{args.remote_dir}')
    remote = RemoteHost(args.host, args.user, args.password, args.port)
    try:
        ensure_remote_docker(remote)
        host_port = choose_host_port(remote)
        remote_env = build_remote_env(local_env, host_port)
        if args.backend_only:
            deploy_backend_only(remote, args.remote_dir, remote_env, google_play_service_account_file)
        else:
            ensure_admin_bot_token_is_configured(remote_env)
            ensure_remote_cron(remote)
            ensure_remote_admin_bot_token_is_unique(remote, args.remote_dir, remote_env)
            deploy(remote, args.remote_dir, remote_env, google_play_service_account_file)
            install_admin_bot_watchdog(
                remote,
                args.remote_dir,
                heartbeat_path=local_env.get('ADMIN_BOT_HEARTBEAT_PATH', '/tmp/admin_bot.heartbeat'),
                max_age_seconds=int(local_env.get('ADMIN_BOT_WATCHDOG_MAX_AGE_SECONDS', '180') or 180),
            )
        health_payload = wait_for_health(remote, args.remote_dir, host_port)
        _, ps_out, _ = remote.run(f"cd '{args.remote_dir}' && docker compose ps")
        print(f'Host port: {host_port}')
        print('Health check OK:')
        print(health_payload)
        print('\nDocker Compose status:')
        print(ps_out)
    finally:
        remote.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
