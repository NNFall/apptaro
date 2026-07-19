from __future__ import annotations

import argparse
import json
import os
import posixpath
import shlex
import ssl
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from urllib.parse import urljoin, urlparse
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REMOTE_DIR = '/root/ASapptaro'
DEFAULT_HOST_PORT = 8023
DEFAULT_COMMAND_TIMEOUT_SECONDS = 600.0
BACKEND_SERVICE_NAME = 'asapptaro_backend'
ADMIN_BOT_SERVICE_NAME = 'asapptaro_admin_bot'
EXPECTED_HEALTH_SERVICE = 'ASapptaro Backend'

PRIVATE_KEY_REMOTE_PATH = '/root/ASapptaro/secrets/apple/AuthKey.p8'
ROOT_CERTIFICATES_REMOTE_DIR = '/root/ASapptaro/secrets/apple/root-certificates'

_COMMON_SKIP_NAMES = {
    '.env',
    '.git',
    '.mypy_cache',
    '.pytest_cache',
    '.venv',
    '__pycache__',
}
_SKIP_SUFFIXES = {'.pyc', '.pyo'}
_SECRET_SUFFIXES = {'.key', '.p8', '.pem'}
_SECRET_FILE_NAMES = {'credentials.json', 'service-account.json'}
_BACKEND_SKIP_TOP_LEVEL = {'data', 'logs', 'runtime', 'tests'}
_ADMIN_SKIP_TOP_LEVEL = {'tests'}
_CERTIFICATE_SUFFIXES = {'.cer', '.crt', '.der', '.pem'}
_BACKEND_ENV_KEYS = frozenset({
    'ADMIN_BOT_TOKEN',
    'ADMIN_IDS',
    'APP_STORE_APPLE_ID',
    'APP_STORE_ISSUER_ID',
    'APP_STORE_KEY_ID',
    'APP_VERSION',
    'CORS_ALLOW_ORIGINS',
    'FONT_FALLBACK',
    'FONT_WHITELIST',
    'IMAGE_CONCURRENCY',
    'IMAGE_GENERATION_RETRIES',
    'IMAGE_GENERATION_RETRY_DELAY_SECONDS',
    'KIE_API_KEY',
    'KIE_BASE_URL',
    'KIE_IMAGE_ENDPOINT',
    'KIE_IMAGE_MODEL',
    'KIE_TEXT_ENDPOINT',
    'KIE_TEXT_FALLBACK_MODELS',
    'KIE_TEXT_MODEL',
    'LOG_LEVEL',
    'REPLICATE_API_TOKEN',
    'REPLICATE_BASE_URL',
    'REPLICATE_DEFAULT_INPUT',
    'REPLICATE_MODEL',
    'REPLICATE_POLL_INTERVAL',
    'REPLICATE_TEXT_DEFAULT_INPUT',
    'REPLICATE_TEXT_MODEL',
    'REPLICATE_TEXT_PROMPT_FIELD',
    'REPLICATE_TIMEOUT_SECONDS',
    'REPLICATE_WAIT_SECONDS',
    'SUPPORT_MAX_URL',
    'SUPPORT_USERNAME',
})
_ADMIN_ENV_KEYS = frozenset({
    'ADMIN_BOT_POLLING_RETRY_MAX_SECONDS',
    'ADMIN_BOT_POLLING_TIMEOUT_SECONDS',
    'ADMIN_BOT_TOKEN',
    'ADMIN_BOT_USERNAME',
    'ADMIN_IDS',
    'APP_SHARE_URL',
})
_PERSISTENT_RELATIVE_PATHS = (
    'data',
    'backups',
    'temp',
    'logs',
    'templates',
    'tarot',
    'secrets',
    'secrets/apple',
    'secrets/apple/root-certificates',
)


class DeploymentArtifact(NamedTuple):
    local_relative: str
    remote_relative: str
    is_tree: bool


class DeploymentReplacement(NamedTuple):
    destination: str
    backup: str
    had_previous: bool


TreeReplacement = DeploymentReplacement


class DeploymentTransaction:
    def __init__(self, remote) -> None:
        self._remote = remote
        self._replacements: list[DeploymentReplacement] = []

    @property
    def has_replacements(self) -> bool:
        return bool(self._replacements)

    def replace_tree(self, staging: str, destination: str) -> DeploymentReplacement:
        replacement = self._remote.atomic_replace_tree(staging, destination)
        self._replacements.append(replacement)
        return replacement

    def replace_file(self, staging: str, destination: str) -> DeploymentReplacement:
        replacement = self._remote.atomic_replace_file(staging, destination)
        self._replacements.append(replacement)
        return replacement

    def commit(self) -> None:
        replacements = list(self._replacements)
        self._replacements.clear()
        errors: list[Exception] = []
        for replacement in replacements:
            try:
                self._remote.commit_replacement(replacement)
            except Exception as error:
                errors.append(error)
        if errors:
            raise RuntimeError(
                f'Failed to clean up {len(errors)} deployment artifact backup(s).'
            ) from errors[0]

    def rollback(self) -> None:
        replacements = list(reversed(self._replacements))
        self._replacements.clear()
        errors: list[Exception] = []
        for replacement in replacements:
            try:
                self._remote.rollback_replacement(replacement)
            except Exception as error:
                errors.append(error)
        if errors:
            raise RuntimeError(
                f'Failed to roll back {len(errors)} deployment artifact replacement(s).'
            ) from errors[0]


TreeDeploymentTransaction = DeploymentTransaction


def artifact_manifest(repo_root: Path = REPO_ROOT) -> tuple[DeploymentArtifact, ...]:
    del repo_root
    return (
        DeploymentArtifact('backend', 'backend', True),
        DeploymentArtifact('telegram_admin_bot', 'telegram_admin_bot', True),
        DeploymentArtifact('backend/runtime/templates', 'templates', True),
        DeploymentArtifact('backend/runtime/tarot', 'tarot', True),
        DeploymentArtifact('deploy/apple/docker-compose.yml', 'docker-compose.yml', False),
    )


def validate_remote_dir(candidate: str) -> str:
    if not candidate or not candidate.startswith('/'):
        raise ValueError('Remote path must be absolute.')
    if '..' in PurePosixPath(candidate).parts:
        raise ValueError('Remote path must not contain parent traversal.')

    normalized = posixpath.normpath(candidate)
    if normalized != DEFAULT_REMOTE_DIR and not normalized.startswith(DEFAULT_REMOTE_DIR + '/'):
        raise ValueError(f'Remote path must stay under {DEFAULT_REMOTE_DIR}: {candidate}')
    return normalized


def validate_deployment_root(candidate: str) -> str:
    normalized = validate_remote_dir(candidate)
    if normalized != DEFAULT_REMOTE_DIR:
        raise ValueError(f'Apple production stack must deploy exactly to {DEFAULT_REMOTE_DIR}.')
    return normalized


def safe_remote_child(remote_dir: str, relative: str) -> str:
    root = validate_remote_dir(remote_dir)
    candidate = posixpath.normpath(posixpath.join(root, relative))
    return validate_remote_dir(candidate)


def validate_health_url(url: str, *, production: bool) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Health URL must be an absolute HTTP(S) URL.')
    if production and parsed.scheme != 'https':
        raise ValueError('Production health URL must use HTTPS.')
    if parsed.username or parsed.password:
        raise ValueError('Health URL must not contain credentials.')
    if parsed.query or parsed.fragment:
        raise ValueError('Health URL must not contain a query or fragment.')
    return value


def _compose_text(repo_root: Path) -> str:
    return (repo_root / 'deploy' / 'apple' / 'docker-compose.yml').read_text(encoding='utf-8')


def validate_local_assets(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    missing: list[str] = []
    for artifact in artifact_manifest(repo_root):
        path = repo_root / Path(artifact.local_relative)
        if artifact.is_tree and not path.is_dir():
            missing.append(artifact.local_relative)
        elif not artifact.is_tree and not path.is_file():
            missing.append(artifact.local_relative)

    runbook = repo_root / 'docs' / 'APP_STORE_RELEASE.md'
    if not runbook.is_file():
        missing.append('docs/APP_STORE_RELEASE.md')
    env_example = repo_root / 'deploy' / 'apple' / '.env.example'
    if not env_example.is_file():
        missing.append('deploy/apple/.env.example')
    readiness_check = repo_root / 'scripts' / 'check_asapptaro_deployment.py'
    if not readiness_check.is_file():
        missing.append('scripts/check_asapptaro_deployment.py')
    if missing:
        raise FileNotFoundError('Missing Apple deployment assets: ' + ', '.join(missing))

    compose = _compose_text(repo_root)
    required_fragments = (
        'asapptaro_backend:',
        'asapptaro_admin_bot:',
        'container_name: asapptaro_backend',
        'container_name: asapptaro_admin_bot',
        '/root/ASapptaro/data:/data',
        'DATABASE_PATH: /data/asapptaro.db',
        '127.0.0.1:8023:8000',
        'restart: unless-stopped',
        'driver: json-file',
    )
    for fragment in required_fragments:
        if fragment not in compose:
            raise ValueError(f'Apple Compose is missing required setting: {fragment}')
    if '/root/PMapptaro' in compose:
        raise ValueError('Apple Compose must not reference /root/PMapptaro.')

    return {
        'remote_dir': DEFAULT_REMOTE_DIR,
        'host_port': DEFAULT_HOST_PORT,
        'services': [BACKEND_SERVICE_NAME, ADMIN_BOT_SERVICE_NAME],
        'artifacts': [item.local_relative for item in artifact_manifest(repo_root)],
    }


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _format_env_value(value: str) -> str:
    if value == '':
        return ''
    if any(character.isspace() for character in value) or any(
        character in value for character in '#"\''
    ):
        return json.dumps(value, ensure_ascii=False)
    return value


def build_remote_env(local_values: dict[str, str], host_port: int) -> str:
    values = {
        key: value
        for key, value in local_values.items()
        if key in _BACKEND_ENV_KEYS
    }
    for local_only_key in (
        'APP_STORE_PRIVATE_KEY_LOCAL_FILE',
        'APP_STORE_ROOT_CERTIFICATES_LOCAL_DIR',
        'ASAPPTARO_SSH_PASSWORD',
    ):
        values.pop(local_only_key, None)

    values.update(
        {
            'APP_NAME': EXPECTED_HEALTH_SERVICE,
            'APP_ENV': 'production',
            'APP_HOST': '0.0.0.0',
            'APP_PORT': '8000',
            'HOST_PORT': str(host_port),
            'DATA_DIR': '/data',
            'DATABASE_PATH': '/data/asapptaro.db',
            'TEMP_DIR': '/app/runtime/temp',
            'TEMPLATES_DIR': '/app/runtime/templates',
            'TAROT_CARDS_DIR': '/app/runtime/tarot/cards',
            'TAROT_BACKGROUND_PATH': '/app/runtime/tarot/backgrounds/main.png',
            'TAROT_LAYOUT_PATH': '/app/runtime/tarot/layout.json',
            'APP_STORE_BUNDLE_ID': 'com.nexwit.tarotreaderai',
            'APP_STORE_PRIVATE_KEY_PATH': '/run/secrets/apple/AuthKey.p8',
            'APP_STORE_ROOT_CERTIFICATES_DIR': '/run/secrets/apple/root-certificates',
            'APP_STORE_ENABLE_ONLINE_CHECKS': '1',
            'ENABLE_LEGACY_YOOKASSA_BILLING': '0',
            'GOOGLE_PLAY_TEST_MODE': '0',
        }
    )
    return ''.join(
        f'{key}={_format_env_value(values[key])}\n'
        for key in sorted(values)
    )


def build_remote_admin_env(local_values: dict[str, str]) -> str:
    values = {
        key: value
        for key, value in local_values.items()
        if key in _ADMIN_ENV_KEYS
    }
    values.update(
        {
            'APP_ENV': 'production',
            'DATABASE_PATH': '/data/asapptaro.db',
            'ADMIN_DATABASE_PATH': '/data/asapptaro.db',
            'ADMIN_BOT_HEARTBEAT_PATH': '/tmp/admin_bot.heartbeat',
        }
    )
    return ''.join(
        f'{key}={_format_env_value(values[key])}\n'
        for key in sorted(values)
    )


def validate_runtime_env(values: dict[str, str]) -> None:
    required = (
        'APP_STORE_APPLE_ID',
        'APP_STORE_KEY_ID',
        'APP_STORE_ISSUER_ID',
        'ADMIN_BOT_TOKEN',
        'ADMIN_IDS',
    )
    missing = [key for key in required if not values.get(key, '').strip()]
    if missing:
        raise ValueError('Missing required deployment environment keys: ' + ', '.join(missing))
    try:
        if int(values['APP_STORE_APPLE_ID']) <= 0:
            raise ValueError
    except ValueError as error:
        raise ValueError('APP_STORE_APPLE_ID must be a positive integer.') from error


def resolve_private_key_file(explicit: str, env_values: dict[str, str]) -> Path:
    raw = explicit.strip() or env_values.get('APP_STORE_PRIVATE_KEY_LOCAL_FILE', '').strip()
    if not raw:
        raise ValueError('Pass --apple-private-key-file or APP_STORE_PRIVATE_KEY_LOCAL_FILE.')
    path = Path(raw).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.p8':
        raise FileNotFoundError(f'Apple .p8 private key was not found: {path}')
    return path


def resolve_root_certificates_dir(explicit: str, env_values: dict[str, str]) -> tuple[Path, list[Path]]:
    raw = explicit.strip() or env_values.get('APP_STORE_ROOT_CERTIFICATES_LOCAL_DIR', '').strip()
    if not raw:
        raise ValueError(
            'Pass --apple-root-certificates-dir or APP_STORE_ROOT_CERTIFICATES_LOCAL_DIR.'
        )
    directory = Path(raw).expanduser().resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f'Apple root certificates directory was not found: {directory}')
    certificates = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in _CERTIFICATE_SUFFIXES
    )
    if not certificates:
        raise FileNotFoundError(f'No Apple root certificates found in: {directory}')
    return directory, certificates


def _skip_upload_path(artifact: DeploymentArtifact, relative: Path) -> bool:
    lowered_parts = tuple(part.lower() for part in relative.parts)
    if any(part in _COMMON_SKIP_NAMES for part in relative.parts):
        return True
    if relative.as_posix().lower() != '.env.example' and any(
        part.startswith('.env') for part in lowered_parts
    ):
        return True
    if relative.suffix.lower() in _SKIP_SUFFIXES:
        return True
    if relative.suffix.lower() in _SECRET_SUFFIXES:
        return True
    if relative.name.lower() in _SECRET_FILE_NAMES:
        return True
    if 'service-account' in relative.name.lower():
        return True
    if artifact.local_relative == 'backend' and relative.parts:
        return relative.parts[0] in _BACKEND_SKIP_TOP_LEVEL
    if artifact.local_relative == 'telegram_admin_bot' and relative.parts:
        return relative.parts[0] in _ADMIN_SKIP_TOP_LEVEL
    return False


def build_database_backup_command(
    remote_dir: str,
    *,
    timestamp: datetime | None = None,
) -> str:
    root = validate_deployment_root(remote_dir)
    stamp = (timestamp or datetime.now(UTC)).astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')
    source = safe_remote_child(root, 'data/asapptaro.db')
    backup_dir = safe_remote_child(root, 'backups')
    destination = safe_remote_child(root, f'backups/asapptaro.db.{stamp}.bak')
    python_code = (
        'from pathlib import Path; import os, sqlite3; '
        f'src=Path({source!r}); dst=Path({destination!r}); '
        'src.exists() and dst.parent.mkdir(parents=True, exist_ok=True); '
        'source=sqlite3.connect(str(src), timeout=30) if src.exists() else None; '
        'target=sqlite3.connect(str(dst)) if source is not None else None; '
        'source is not None and source.backup(target); '
        'target is not None and target.close(); '
        'source is not None and source.close(); '
        'dst.exists() and os.chmod(dst, 0o600)'
    )
    return f'mkdir -p {shlex.quote(backup_dir)} && python3 -c {shlex.quote(python_code)}'


def build_compose_up_command(remote_dir: str) -> str:
    root = validate_deployment_root(remote_dir)
    return (
        f'cd {shlex.quote(root)} && '
        'docker compose --project-name asapptaro --file docker-compose.yml '
        'up -d --build --remove-orphans --force-recreate'
    )


def build_compose_ps_command(remote_dir: str) -> str:
    root = validate_deployment_root(remote_dir)
    return (
        f'cd {shlex.quote(root)} && '
        'docker compose --project-name asapptaro --file docker-compose.yml '
        'ps --format json'
    )


def validate_compose_status(raw: str) -> None:
    stripped = raw.strip()
    if not stripped:
        raise RuntimeError('Docker Compose returned no service status.')
    try:
        if stripped.startswith('['):
            payload = json.loads(stripped)
        else:
            payload = [json.loads(line) for line in stripped.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise RuntimeError('Docker Compose returned invalid JSON status.') from error

    services = {
        str(item.get('Service', '')): item
        for item in payload
        if isinstance(item, dict)
    }
    for service_name in (BACKEND_SERVICE_NAME, ADMIN_BOT_SERVICE_NAME):
        item = services.get(service_name)
        if item is None:
            raise RuntimeError(f'{service_name} is missing from Docker Compose status.')
        state = str(item.get('State', '')).lower()
        health = str(item.get('Health', '')).lower()
        if state != 'running' or health != 'healthy':
            raise RuntimeError(
                f'{service_name} is not healthy: state={state or "unknown"}, '
                f'health={health or "unknown"}.'
            )


def wait_for_compose_health(
    remote,
    remote_dir: str,
    timeout_seconds: int = 240,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_error = 'no status'
    command = build_compose_ps_command(remote_dir)
    while time.monotonic() < deadline:
        exit_code, out, err = remote.run(command, check=False)
        if exit_code == 0:
            try:
                validate_compose_status(out)
                return out
            except RuntimeError as error:
                last_error = str(error)
        else:
            last_error = err.strip() or f'docker compose ps exited with {exit_code}'
        time.sleep(3)
    raise RuntimeError(f'Docker Compose health check failed: {last_error}')


def restart_stack(
    remote,
    remote_dir: str,
    *,
    timestamp: datetime | None = None,
) -> None:
    remote.run(build_database_backup_command(remote_dir, timestamp=timestamp))
    remote.run(build_compose_up_command(remote_dir))


def rollback_deployment(
    remote,
    remote_dir: str,
    transaction: DeploymentTransaction,
    health_timeout_seconds: int,
) -> None:
    transaction.rollback()
    remote.run(build_compose_up_command(remote_dir))
    wait_for_compose_health(remote, remote_dir, health_timeout_seconds)


@contextmanager
def transactional_deployment(
    remote,
    remote_dir: str,
    health_timeout_seconds: int,
):
    transaction = DeploymentTransaction(remote)
    try:
        yield transaction
    except Exception:
        if transaction.has_replacements:
            try:
                rollback_deployment(
                    remote,
                    remote_dir,
                    transaction,
                    health_timeout_seconds,
                )
            except Exception as rollback_error:
                raise RuntimeError(
                    'Deployment failed and the previous trees could not be fully restored.'
                ) from rollback_error
        raise
    else:
        transaction.commit()


transactional_tree_deployment = transactional_deployment


class RemoteHost:
    def __init__(
        self,
        host: str,
        user: str,
        port: int,
        *,
        password: str = '',
        ssh_key_file: str = '',
        command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import paramiko
        except ImportError as error:  # pragma: no cover - deployment environment only
            raise RuntimeError('Install paramiko before remote deployment.') from error

        if command_timeout_seconds <= 0:
            raise ValueError('Remote command timeout must be positive.')

        self._command_timeout_seconds = command_timeout_seconds
        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        self._client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self._client.connect(
            hostname=host,
            username=user,
            port=port,
            password=password or None,
            key_filename=ssh_key_file or None,
            timeout=20,
            allow_agent=True,
            look_for_keys=True,
        )
        self._sftp = self._client.open_sftp()

    def close(self) -> None:
        self._sftp.close()
        self._client.close()

    def run(
        self,
        command: str,
        check: bool = True,
        timeout_seconds: float | None = None,
    ) -> tuple[int, str, str]:
        timeout = (
            getattr(self, '_command_timeout_seconds', DEFAULT_COMMAND_TIMEOUT_SECONDS)
            if timeout_seconds is None
            else timeout_seconds
        )
        if timeout <= 0:
            raise ValueError('Remote command timeout must be positive.')

        _stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        channel = stdout.channel
        out_chunks: list[bytes] = []
        err_chunks: list[bytes] = []
        deadline = time.monotonic() + timeout
        try:
            while True:
                drained = False
                while channel.recv_ready():
                    out_chunks.append(channel.recv(65536))
                    drained = True
                while channel.recv_stderr_ready():
                    err_chunks.append(channel.recv_stderr(65536))
                    drained = True
                if channel.exit_status_ready() and not (
                    channel.recv_ready() or channel.recv_stderr_ready()
                ):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f'Remote command timed out after {timeout:g} seconds: {command}'
                    )
                if not drained:
                    time.sleep(0.01)
            exit_code = channel.recv_exit_status()
        except Exception:
            channel.close()
            raise
        out = b''.join(out_chunks).decode('utf-8', errors='replace')
        err = b''.join(err_chunks).decode('utf-8', errors='replace')
        if check and exit_code != 0:
            raise RuntimeError(
                f'Remote command failed ({exit_code}).\nSTDOUT:\n{out}\nSTDERR:\n{err}'
            )
        return exit_code, out, err

    def ensure_dir(self, remote_dir: str, mode: int | None = None) -> None:
        self.run(f'mkdir -p {shlex.quote(remote_dir)}')
        if mode is not None:
            self.run(f'chmod {mode:o} {shlex.quote(remote_dir)}')

    def remove_tree(self, remote_dir: str) -> None:
        normalized = validate_remote_dir(remote_dir)
        if normalized == DEFAULT_REMOTE_DIR:
            raise ValueError('Refusing to remove the Apple deployment root.')
        self.run(f'rm -rf -- {shlex.quote(normalized)}')

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        mode: int | None = None,
        transaction: DeploymentTransaction | None = None,
    ) -> None:
        destination, temporary = _atomic_upload_paths(remote_path)
        parent = posixpath.dirname(destination)
        if parent:
            self.ensure_dir(parent)
        try:
            self._sftp.put(str(local_path), temporary)
            if mode is not None:
                self.run(f'chmod {mode:o} {shlex.quote(temporary)}')
            if transaction is None:
                self.run(
                    f'mv -fT -- {shlex.quote(temporary)} {shlex.quote(destination)}'
                )
            else:
                transaction.replace_file(temporary, destination)
        except Exception:
            self.run(f'rm -f -- {shlex.quote(temporary)}', check=False)
            raise

    def upload_text(
        self,
        content: str,
        remote_path: str,
        mode: int | None = None,
        transaction: DeploymentTransaction | None = None,
    ) -> None:
        destination, temporary = _atomic_upload_paths(remote_path)
        parent = posixpath.dirname(destination)
        if parent:
            self.ensure_dir(parent)
        try:
            with self._sftp.file(temporary, 'w') as remote_file:
                remote_file.write(content)
            if mode is not None:
                self.run(f'chmod {mode:o} {shlex.quote(temporary)}')
            if transaction is None:
                self.run(
                    f'mv -fT -- {shlex.quote(temporary)} {shlex.quote(destination)}'
                )
            else:
                transaction.replace_file(temporary, destination)
        except Exception:
            self.run(f'rm -f -- {shlex.quote(temporary)}', check=False)
            raise

    def upload_tree(
        self,
        local_root: Path,
        remote_root: str,
        artifact: DeploymentArtifact,
    ) -> None:
        for path in sorted(local_root.rglob('*')):
            relative = path.relative_to(local_root)
            if _skip_upload_path(artifact, relative):
                continue
            if path.is_symlink():
                raise ValueError(f'Refusing to upload symlink: {path}')
            remote_path = posixpath.join(remote_root, *relative.parts)
            if path.is_dir():
                self.ensure_dir(remote_path)
            elif path.is_file():
                self.upload_file(path, remote_path)

    def _atomic_replace(
        self,
        staging: str,
        destination: str,
    ) -> DeploymentReplacement:
        staged = validate_remote_dir(staging)
        target = validate_remote_dir(destination)
        if target == DEFAULT_REMOTE_DIR:
            raise ValueError('Refusing to replace the Apple deployment root.')
        backup = validate_remote_dir(f'{target}.previous-{uuid4().hex}')
        shell = (
            'set -eu; '
            f'rm -rf -- {shlex.quote(backup)}; '
            'had_previous=0; '
            f'if [ -e {shlex.quote(target)} ] || [ -L {shlex.quote(target)} ]; then '
            f'mv -T -- {shlex.quote(target)} {shlex.quote(backup)}; had_previous=1; fi; '
            f'if mv -T -- {shlex.quote(staged)} {shlex.quote(target)}; then '
            "printf '__ASAPPTARO_HAD_PREVIOUS__=%s\\n' \"$had_previous\"; "
            'else '
            f'if [ -e {shlex.quote(backup)} ] || [ -L {shlex.quote(backup)} ]; then '
            f'mv -T -- {shlex.quote(backup)} {shlex.quote(target)}; fi; '
            'exit 1; fi'
        )
        _code, out, _err = self.run(shell)
        marker = '__ASAPPTARO_HAD_PREVIOUS__='
        status = next(
            (line.removeprefix(marker) for line in out.splitlines() if line.startswith(marker)),
            '',
        )
        if status not in {'0', '1'}:
            raise RuntimeError('Remote deployment artifact swap did not report backup state.')
        return DeploymentReplacement(target, backup, status == '1')

    def atomic_replace_tree(
        self,
        staging: str,
        destination: str,
    ) -> DeploymentReplacement:
        return self._atomic_replace(staging, destination)

    def atomic_replace_file(
        self,
        staging: str,
        destination: str,
    ) -> DeploymentReplacement:
        return self._atomic_replace(staging, destination)

    def commit_replacement(self, replacement: DeploymentReplacement) -> None:
        target, backup = _validate_deployment_replacement(replacement)
        del target
        self.run(f'rm -rf -- {shlex.quote(backup)}')

    def rollback_replacement(self, replacement: DeploymentReplacement) -> None:
        target, backup = _validate_deployment_replacement(replacement)
        restore = ''
        if replacement.had_previous:
            restore = (
                f'test -e {shlex.quote(backup)} || test -L {shlex.quote(backup)}; '
                f'mv -T -- {shlex.quote(backup)} {shlex.quote(target)}; '
            )
        else:
            restore = f'rm -rf -- {shlex.quote(backup)}; '
        self.run(
            'set -eu; '
            f'rm -rf -- {shlex.quote(target)}; '
            + restore
        )


def _validate_deployment_replacement(
    replacement: DeploymentReplacement,
) -> tuple[str, str]:
    target = validate_remote_dir(replacement.destination)
    backup = validate_remote_dir(replacement.backup)
    if target == DEFAULT_REMOTE_DIR:
        raise ValueError('Refusing to replace the Apple deployment root.')
    if not backup.startswith(f'{target}.previous-'):
        raise ValueError('Tree backup path does not match its deployment target.')
    return target, backup


def _atomic_upload_paths(remote_path: str) -> tuple[str, str]:
    destination = validate_remote_dir(remote_path)
    if destination == DEFAULT_REMOTE_DIR:
        raise ValueError('Refusing to replace the Apple deployment root.')
    temporary = f'{destination}.upload-{uuid4().hex}'
    validate_remote_dir(temporary)
    return destination, temporary


def resolve_remote_dir(remote: RemoteHost, candidate: str) -> str:
    lexical = validate_deployment_root(candidate)
    _code, out, _err = remote.run(f'readlink -m -- {shlex.quote(lexical)}')
    resolved = validate_remote_dir(out.strip())
    if resolved != lexical:
        raise ValueError(
            f'Remote deployment root resolves outside the approved path: {lexical} -> {resolved}'
        )
    return resolved


def ensure_remote_prerequisites(remote: RemoteHost, host_port: int) -> None:
    for command, label in (
        ('docker --version', 'Docker'),
        ('docker compose version', 'Docker Compose'),
        ('python3 --version', 'Python 3'),
        ('command -v ss', 'ss'),
    ):
        exit_code, _out, _err = remote.run(command, check=False)
        if exit_code != 0:
            raise RuntimeError(f'{label} is required on the remote host.')

    _code, listeners, _err = remote.run(
        f"ss -H -ltn 'sport = :{host_port}'",
        check=False,
    )
    if not listeners.strip():
        return
    _code, current_ports, _err = remote.run(
        "docker ps --filter 'name=^/asapptaro_backend$' --format '{{.Ports}}'",
        check=False,
    )
    if f':{host_port}->8000/tcp' not in current_ports:
        raise RuntimeError(f'Host port {host_port} is already occupied by another service.')


def prepare_remote_directories(remote: RemoteHost, remote_dir: str) -> None:
    root = validate_deployment_root(remote_dir)
    remote.ensure_dir(root, mode=700)
    for relative in ('data', 'backups', 'temp', 'logs', 'templates', 'tarot'):
        remote.ensure_dir(safe_remote_child(root, relative), mode=700)
    remote.ensure_dir(safe_remote_child(root, 'secrets/apple'), mode=700)
    remote.ensure_dir(ROOT_CERTIFICATES_REMOTE_DIR, mode=700)


def validate_persistent_paths(remote: RemoteHost, remote_dir: str) -> None:
    root = validate_deployment_root(remote_dir)
    for relative in _PERSISTENT_RELATIVE_PATHS:
        lexical = safe_remote_child(root, relative)
        _code, out, _err = remote.run(f'readlink -m -- {shlex.quote(lexical)}')
        resolved = posixpath.normpath(out.strip())
        if resolved != lexical:
            raise ValueError(
                f'Apple persistent path must not resolve elsewhere: '
                f'{lexical} -> {resolved}'
            )


def upload_artifacts(
    remote: RemoteHost,
    repo_root: Path,
    remote_dir: str,
    transaction: DeploymentTransaction,
) -> None:
    root = validate_deployment_root(remote_dir)
    for artifact in artifact_manifest(repo_root):
        local_path = repo_root / Path(artifact.local_relative)
        remote_path = safe_remote_child(root, artifact.remote_relative)
        if artifact.is_tree:
            staging = validate_remote_dir(f'{remote_path}.staging-{uuid4().hex}')
            remote.ensure_dir(staging, mode=700)
            try:
                remote.upload_tree(local_path, staging, artifact)
                transaction.replace_tree(staging, remote_path)
            except Exception:
                remote.remove_tree(staging)
                raise
        else:
            remote.upload_file(
                local_path,
                remote_path,
                mode=600,
                transaction=transaction,
            )


def upload_apple_credentials(
    remote: RemoteHost,
    private_key_file: Path,
    certificate_files: list[Path],
    transaction: DeploymentTransaction,
) -> None:
    remote.upload_file(
        private_key_file,
        PRIVATE_KEY_REMOTE_PATH,
        mode=600,
        transaction=transaction,
    )
    staging = validate_remote_dir(
        f'{ROOT_CERTIFICATES_REMOTE_DIR}.staging-{uuid4().hex}'
    )
    remote.ensure_dir(staging, mode=700)
    try:
        for certificate in certificate_files:
            destination = validate_remote_dir(
                posixpath.join(staging, certificate.name)
            )
            remote.upload_file(certificate, destination, mode=600)
        transaction.replace_tree(staging, ROOT_CERTIFICATES_REMOTE_DIR)
    except Exception:
        remote.remove_tree(staging)
        raise


def upload_runtime_envs(
    remote: RemoteHost,
    remote_dir: str,
    backend_env: str,
    admin_env: str,
    transaction: DeploymentTransaction,
) -> None:
    root = validate_deployment_root(remote_dir)
    remote.upload_text(
        backend_env,
        safe_remote_child(root, '.env.backend'),
        mode=600,
        transaction=transaction,
    )
    remote.upload_text(
        admin_env,
        safe_remote_child(root, '.env.admin'),
        mode=600,
        transaction=transaction,
    )


def is_expected_health_response(raw: str) -> bool:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(payload, dict)
        and payload.get('status') == 'ok'
        and payload.get('service') == EXPECTED_HEALTH_SERVICE
        and payload.get('environment') == 'production'
    )


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        if urlparse(target).scheme.lower() != 'https':
            raise urllib.error.HTTPError(
                target,
                code,
                'Refusing health redirect to a non-HTTPS URL.',
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, target)


def wait_for_external_health(url: str, timeout_seconds: int = 180) -> str:
    target = validate_health_url(url, production=True)
    deadline = time.monotonic() + timeout_seconds
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        HTTPSOnlyRedirectHandler(),
    )
    last_error = 'no response'
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(target, headers={'Accept': 'application/json'})
            with opener.open(request, timeout=10) as response:
                validate_health_url(response.geturl(), production=True)
                raw = response.read().decode('utf-8', errors='replace')
            if is_expected_health_response(raw):
                return raw
            last_error = 'unexpected health payload'
        except (OSError, urllib.error.URLError, ValueError) as error:
            last_error = str(error)
        time.sleep(3)
    raise RuntimeError(f'HTTPS health check failed for {target}: {last_error}')


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Safely deploy the isolated ASapptaro App Store backend stack.'
    )
    parser.add_argument('--local-validate', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--host', default=os.getenv('ASAPPTARO_REMOTE_HOST', ''))
    parser.add_argument('--user', default=os.getenv('ASAPPTARO_REMOTE_USER', 'root'))
    parser.add_argument('--port', type=int, default=int(os.getenv('ASAPPTARO_REMOTE_PORT', '22')))
    parser.add_argument('--password', default=os.getenv('ASAPPTARO_SSH_PASSWORD', ''))
    parser.add_argument('--ssh-key-file', default=os.getenv('ASAPPTARO_SSH_KEY_FILE', ''))
    parser.add_argument('--remote-dir', default=DEFAULT_REMOTE_DIR)
    parser.add_argument('--host-port', type=int, default=DEFAULT_HOST_PORT)
    parser.add_argument('--env-file', default=str(REPO_ROOT / '.env'))
    parser.add_argument('--apple-private-key-file', default='')
    parser.add_argument('--apple-root-certificates-dir', default='')
    parser.add_argument('--health-url', default=os.getenv('ASAPPTARO_HEALTH_URL', ''))
    parser.add_argument('--health-timeout', type=int, default=180)
    parser.add_argument(
        '--command-timeout',
        type=float,
        default=float(
            os.getenv('ASAPPTARO_SSH_COMMAND_TIMEOUT', DEFAULT_COMMAND_TIMEOUT_SECONDS)
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    local_summary = validate_local_assets(REPO_ROOT)
    validate_deployment_root(args.remote_dir)
    if args.host_port != DEFAULT_HOST_PORT:
        raise ValueError(f'ASapptaro production host port must remain {DEFAULT_HOST_PORT}.')

    if args.local_validate:
        print(json.dumps(local_summary, ensure_ascii=False, indent=2))
        return 0

    env_file = Path(args.env_file).expanduser().resolve()
    if not env_file.is_file():
        raise FileNotFoundError(f'Deployment env file was not found: {env_file}')
    env_values = _read_env_file(env_file)
    validate_runtime_env(env_values)
    private_key_file = resolve_private_key_file(args.apple_private_key_file, env_values)
    _certificate_dir, certificate_files = resolve_root_certificates_dir(
        args.apple_root_certificates_dir,
        env_values,
    )
    health_url = validate_health_url(args.health_url, production=True)
    remote_env = build_remote_env(env_values, args.host_port)
    remote_admin_env = build_remote_admin_env(env_values)

    if args.dry_run:
        print(
            json.dumps(
                {
                    **local_summary,
                    'host': args.host or '<required for deployment>',
                    'health_url': health_url,
                    'private_key': 'configured',
                    'root_certificates': len(certificate_files),
                    'network_actions': False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not args.host:
        raise ValueError('Pass --host or set ASAPPTARO_REMOTE_HOST.')

    remote = RemoteHost(
        args.host,
        args.user,
        args.port,
        password=args.password,
        ssh_key_file=args.ssh_key_file,
        command_timeout_seconds=args.command_timeout,
    )
    try:
        with transactional_deployment(
            remote,
            args.remote_dir,
            args.health_timeout,
        ) as transaction:
            remote_dir = resolve_remote_dir(remote, args.remote_dir)
            ensure_remote_prerequisites(remote, args.host_port)
            validate_persistent_paths(remote, remote_dir)
            prepare_remote_directories(remote, remote_dir)
            validate_persistent_paths(remote, remote_dir)
            upload_artifacts(remote, REPO_ROOT, remote_dir, transaction)
            upload_apple_credentials(
                remote,
                private_key_file,
                certificate_files,
                transaction,
            )
            upload_runtime_envs(
                remote,
                remote_dir,
                remote_env,
                remote_admin_env,
                transaction,
            )
            restart_stack(remote, remote_dir)
            status = wait_for_compose_health(remote, remote_dir, args.health_timeout)
            health_payload = wait_for_external_health(health_url, args.health_timeout)
        print('HTTPS health check passed.')
        print(health_payload)
        print(status)
    finally:
        remote.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
