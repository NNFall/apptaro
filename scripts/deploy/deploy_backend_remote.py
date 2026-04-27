from __future__ import annotations

import argparse
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
TEMPLATES_DIR = REPO_ROOT / 'telegrambot' / 'media' / 'templates'
COMPOSE_FILE = REPO_ROOT / 'docker-compose.backend.yml'

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
    parser = argparse.ArgumentParser(description='Deploy AppSlides backend to a remote Docker host.')
    parser.add_argument('--host', required=True)
    parser.add_argument('--user', default='root')
    parser.add_argument('--password', required=True)
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--remote-dir', default='/root/appslides')
    return parser.parse_args()


def load_local_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (
        REPO_ROOT / '.env',
        BACKEND_DIR / '.env',
        REPO_ROOT / 'telegrambot' / '.env',
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
    env: dict[str, str] = {
        'APP_NAME': local_env.get('APP_NAME', 'AppSlides Backend'),
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
        'DATABASE_PATH': '/data/appslides.db',
        'TEMP_DIR': '/app/runtime/temp',
        'TEMPLATES_DIR': '/app/runtime/templates',
        'IMAGE_CONCURRENCY': local_env.get('IMAGE_CONCURRENCY', '5'),
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
        'SUPPORT_USERNAME',
        'OFFER_URL',
        'AUTO_RENEW_INTERVAL',
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
    for path in (BACKEND_DIR, TEMPLATES_DIR, COMPOSE_FILE):
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


def deploy(remote: RemoteHost, remote_dir: str, remote_env: str) -> None:
    backend_remote = posixpath.join(remote_dir, 'backend')
    templates_remote = posixpath.join(remote_dir, 'templates')
    remote.ensure_dir(remote_dir)
    for name in ('data', 'temp', 'logs'):
        remote.ensure_dir(posixpath.join(remote_dir, name))

    for path in (backend_remote, templates_remote):
        remote.remove_tree(path)

    remote.upload_tree(BACKEND_DIR, backend_remote, skip_backend_filters=True)
    remote.upload_tree(TEMPLATES_DIR, templates_remote)
    remote.upload_file(COMPOSE_FILE, posixpath.join(remote_dir, 'docker-compose.yml'))
    remote.upload_text(remote_env, posixpath.join(remote_dir, '.env'))

    remote.run(f"cd '{remote_dir}' && docker compose down --remove-orphans", check=False)
    remote.run(f"cd '{remote_dir}' && docker compose up -d --build --remove-orphans")


def wait_for_health(remote: RemoteHost, remote_dir: str, host_port: int, timeout_seconds: int = 180) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        exit_code, out, _ = remote.run(
            f"curl -fsS --max-time 5 http://127.0.0.1:{host_port}/v1/health",
            check=False,
        )
        if exit_code == 0:
            return out.strip()
        time.sleep(3)

    _, logs_out, logs_err = remote.run(
        f"cd '{remote_dir}' && docker compose logs --tail=200",
        check=False,
    )
    raise RuntimeError(f'Health check did not pass in time.\nLOGS:\n{logs_out}\n{logs_err}')


def choose_host_port(remote: RemoteHost, preferred_port: int = 8010) -> int:
    exit_code, out, _ = remote.run(
        f"ss -ltn '( sport = :{preferred_port} )' | sed -n '2,$p'",
        check=False,
    )
    if exit_code == 0 and not out.strip():
        return preferred_port

    exit_code, container_out, _ = remote.run(
        "docker ps --format '{{.Names}} {{.Ports}}' | grep '^appslides_backend '",
        check=False,
    )
    if exit_code == 0 and f':{preferred_port}->' in container_out:
        return preferred_port

    raise RuntimeError(
        f'Host port {preferred_port} is busy. AppSlides mobile client is fixed to this port, '
        'so release the port or update the application configuration before redeploy.'
    )


def main() -> int:
    args = parse_args()
    ensure_required_paths()
    local_env = load_local_env()

    print(f'Deploying backend to {args.user}@{args.host}:{args.remote_dir}')
    remote = RemoteHost(args.host, args.user, args.password, args.port)
    try:
        ensure_remote_docker(remote)
        host_port = choose_host_port(remote)
        remote_env = build_remote_env(local_env, host_port)
        deploy(remote, args.remote_dir, remote_env)
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
