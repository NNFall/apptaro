from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'deploy' / 'deploy_asapptaro_remote.py'
COMPOSE_PATH = REPO_ROOT / 'deploy' / 'apple' / 'docker-compose.yml'
RUNBOOK_PATH = REPO_ROOT / 'docs' / 'APP_STORE_RELEASE.md'
APPLE_ENV_EXAMPLE_PATH = REPO_ROOT / 'deploy' / 'apple' / '.env.example'
CHECK_SCRIPT_PATH = REPO_ROOT / 'scripts' / 'check_asapptaro_deployment.py'


def _load_deploy_module():
    spec = importlib.util.spec_from_file_location('deploy_asapptaro_remote', SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load deployment module: {SCRIPT_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compose_is_isolated_and_persists_only_apple_stack_data() -> None:
    raw = COMPOSE_PATH.read_text(encoding='utf-8')

    assert re.findall(r'^  ([a-z0-9_]+):$', raw, flags=re.MULTILINE) == [
        'asapptaro_backend',
        'asapptaro_admin_bot',
    ]
    assert raw.count('container_name: asapptaro_backend') == 1
    assert raw.count('container_name: asapptaro_admin_bot') == 1
    assert raw.count('- ./.env.backend') == 1
    assert raw.count('- ./.env.admin') == 1
    assert 'ASAPPTARO_ENV_FILE' not in raw
    assert '/root/PMapptaro' not in raw
    assert '/root/ASapptaro/data:/data' in raw
    assert 'DATABASE_PATH: /data/asapptaro.db' in raw
    assert 'ADMIN_DATABASE_PATH: /data/asapptaro.db' in raw
    assert '127.0.0.1:8023:8000' in raw
    assert '${HOST_PORT' not in raw


def test_compose_mounts_apple_credentials_read_only_and_has_runtime_guards() -> None:
    raw = COMPOSE_PATH.read_text(encoding='utf-8')

    assert '/root/ASapptaro/secrets/apple/AuthKey.p8:/run/secrets/apple/AuthKey.p8:ro' in raw
    assert (
        '/root/ASapptaro/secrets/apple/root-certificates:'
        '/run/secrets/apple/root-certificates:ro'
    ) in raw
    assert raw.count('restart: unless-stopped') == 2
    assert raw.count('driver: json-file') == 2
    assert raw.count('max-size: "10m"') == 2
    assert raw.count('max-file: "3"') == 2
    assert raw.count('healthcheck:') == 2


@pytest.mark.parametrize(
    'candidate',
    (
        '/root/PMapptaro',
        '/root/ASapptaro-evil',
        '/root/ASapptaro/../PMapptaro',
        '/tmp/ASapptaro',
        'root/ASapptaro',
        '/',
    ),
)
def test_remote_path_guard_rejects_paths_outside_apple_root(candidate: str) -> None:
    module = _load_deploy_module()

    with pytest.raises(ValueError):
        module.validate_remote_dir(candidate)


def test_remote_path_guard_accepts_root_and_descendants() -> None:
    module = _load_deploy_module()

    assert module.validate_remote_dir('/root/ASapptaro') == '/root/ASapptaro'
    assert module.validate_remote_dir('/root/ASapptaro/staging') == '/root/ASapptaro/staging'


def test_production_health_url_requires_https() -> None:
    module = _load_deploy_module()

    with pytest.raises(ValueError, match='HTTPS'):
        module.validate_health_url('http://example.com/v1/health', production=True)

    assert (
        module.validate_health_url('https://api.example.com/v1/health', production=True)
        == 'https://api.example.com/v1/health'
    )


@pytest.mark.parametrize(
    'url',
    (
        'https://user:password@example.com/v1/health',
        'https://example.com/v1/health#fragment',
        'https://example.com/v1/health?token=secret',
        'ftp://example.com/v1/health',
        'not-a-url',
    ),
)
def test_health_url_rejects_unsafe_or_invalid_values(url: str) -> None:
    module = _load_deploy_module()

    with pytest.raises(ValueError):
        module.validate_health_url(url, production=True)


def test_artifact_manifest_uploads_only_apple_fork_runtime_assets() -> None:
    module = _load_deploy_module()

    artifacts = module.artifact_manifest(REPO_ROOT)
    assert {(item.local_relative, item.remote_relative) for item in artifacts} == {
        ('backend', 'backend'),
        ('telegram_admin_bot', 'telegram_admin_bot'),
        ('backend/runtime/templates', 'templates'),
        ('backend/runtime/tarot', 'tarot'),
        ('deploy/apple/docker-compose.yml', 'docker-compose.yml'),
    }
    assert all(not item.local_relative.startswith('app/') for item in artifacts)
    assert all('.env' not in item.local_relative for item in artifacts)


def test_remote_env_drops_legacy_store_secrets() -> None:
    module = _load_deploy_module()

    rendered = module.build_remote_env(
        {
            'APP_STORE_KEY_ID': 'APPLE_KEY',
            'ADMIN_BOT_TOKEN': 'ADMIN_TOKEN',
            'UNRELATED_SECRET': 'must-not-upload',
            'COMPOSE_FILE': '/root/PMapptaro/docker-compose.yml',
            'COMPOSE_PROJECT_NAME': 'pmapptaro',
            'YOOKASSA_SECRET': 'legacy-yookassa-secret',
            'GOOGLE_PLAY_SERVICE_ACCOUNT_JSON': 'legacy-google-secret',
            'ASAPPTARO_SSH_PASSWORD': 'ssh-secret',
        },
        8023,
    )

    assert 'APP_STORE_KEY_ID=APPLE_KEY' in rendered
    assert 'ADMIN_BOT_TOKEN=ADMIN_TOKEN' in rendered
    assert 'legacy-yookassa-secret' not in rendered
    assert 'legacy-google-secret' not in rendered
    assert 'ssh-secret' not in rendered
    assert 'COMPOSE_FILE' not in rendered
    assert 'COMPOSE_PROJECT_NAME' not in rendered
    assert 'must-not-upload' not in rendered


def test_admin_env_contains_no_backend_provider_or_apple_secrets() -> None:
    module = _load_deploy_module()

    rendered = module.build_remote_admin_env(
        {
            'ADMIN_BOT_TOKEN': 'ADMIN_TOKEN',
            'ADMIN_IDS': '1,2',
            'KIE_API_KEY': 'KIE_SECRET',
            'APP_STORE_KEY_ID': 'APPLE_KEY',
        }
    )

    assert 'ADMIN_BOT_TOKEN=ADMIN_TOKEN' in rendered
    assert 'ADMIN_IDS=1,2' in rendered
    assert 'KIE_SECRET' not in rendered
    assert 'APPLE_KEY' not in rendered


def test_remove_tree_rejects_deployment_root_with_trailing_separator() -> None:
    module = _load_deploy_module()
    remote = object.__new__(module.RemoteHost)
    remote.run = lambda *_args, **_kwargs: pytest.fail('rm must not run')

    with pytest.raises(ValueError, match='deployment root'):
        remote.remove_tree('/root/ASapptaro/')


def test_persistent_paths_reject_symlinks_outside_apple_root() -> None:
    module = _load_deploy_module()

    class FakeRemote:
        def run(self, command: str, check: bool = True):
            if '/root/ASapptaro/data' in command:
                return 0, '/root/PMapptaro/data\n', ''
            path = command.rsplit(' ', 1)[-1].strip("'")
            return 0, f'{path}\n', ''

    with pytest.raises(ValueError, match='persistent path'):
        module.validate_persistent_paths(FakeRemote(), '/root/ASapptaro')


@pytest.mark.parametrize(
    'relative',
    (
        Path('.env.production'),
        Path('AuthKey_PRIVATE.p8'),
        Path('config/service-account.json'),
        Path('config/credentials.json'),
    ),
)
def test_upload_filter_rejects_secret_like_files(relative: Path) -> None:
    module = _load_deploy_module()
    artifact = module.DeploymentArtifact('backend', 'backend', True)

    assert module._skip_upload_path(artifact, relative) is True


def test_upload_filter_keeps_docker_required_env_example() -> None:
    module = _load_deploy_module()
    artifact = module.DeploymentArtifact('backend', 'backend', True)

    assert module._skip_upload_path(artifact, Path('.env.example')) is False


def test_sensitive_upload_atomically_replaces_destination_symlink(tmp_path: Path) -> None:
    module = _load_deploy_module()
    source = tmp_path / 'source.env'
    source.write_text('KEY=value\n', encoding='utf-8')

    class FakeSftp:
        def __init__(self) -> None:
            self.destinations: list[str] = []

        def put(self, local_path: str, remote_path: str) -> None:
            assert local_path == str(source)
            self.destinations.append(remote_path)

    remote = object.__new__(module.RemoteHost)
    remote._sftp = FakeSftp()
    commands: list[str] = []
    remote.ensure_dir = lambda *_args, **_kwargs: None
    remote.run = lambda command, check=True: commands.append(command) or (0, '', '')

    remote.upload_file(source, '/root/ASapptaro/.env', mode=0o600)

    assert remote._sftp.destinations[0] != '/root/ASapptaro/.env'
    assert remote._sftp.destinations[0].startswith('/root/ASapptaro/.env.upload-')
    assert 'mv -fT --' in commands[-1]
    assert commands[-1].endswith(" /root/ASapptaro/.env")


def test_tree_upload_uses_staging_and_atomic_swap() -> None:
    module = _load_deploy_module()

    class FakeRemote:
        def __init__(self) -> None:
            self.uploaded: list[tuple[str, str]] = []
            self.swaps: list[tuple[str, str]] = []
            self.file_swaps: list[tuple[str, str]] = []

        def ensure_dir(self, *_args, **_kwargs) -> None:
            return None

        def upload_tree(self, local_root, remote_root, artifact) -> None:
            self.uploaded.append((artifact.remote_relative, remote_root))

        def upload_file(
            self,
            local_path,
            remote_path,
            mode=None,
            transaction=None,
        ) -> None:
            self.uploaded.append((str(local_path), remote_path))
            if transaction is not None:
                transaction.replace_file(f'{remote_path}.upload-test', remote_path)

        def atomic_replace_tree(self, staging: str, destination: str):
            self.swaps.append((staging, destination))
            return module.TreeReplacement(
                destination=destination,
                backup=f'{destination}.previous-test',
                had_previous=True,
            )

        def atomic_replace_file(self, staging: str, destination: str):
            self.file_swaps.append((staging, destination))
            return module.DeploymentReplacement(
                destination=destination,
                backup=f'{destination}.previous-test',
                had_previous=True,
            )

        def remove_tree(self, *_args, **_kwargs) -> None:
            pytest.fail('live trees must not be deleted before staging is complete')

    remote = FakeRemote()
    transaction = module.TreeDeploymentTransaction(remote)
    module.upload_artifacts(remote, REPO_ROOT, '/root/ASapptaro', transaction)

    tree_uploads = [item for item in remote.uploaded if '.staging-' in item[1]]
    assert len(tree_uploads) == 4
    assert len(remote.swaps) == 4
    assert remote.file_swaps == [
        ('/root/ASapptaro/docker-compose.yml.upload-test', '/root/ASapptaro/docker-compose.yml')
    ]
    assert all('.staging-' in staging for staging, _ in remote.swaps)


def test_all_final_mutable_file_uploads_join_release_transaction(tmp_path: Path) -> None:
    module = _load_deploy_module()

    class RecordingRemote:
        def __init__(self) -> None:
            self.transactional_files: list[str] = []
            self.modes: list[int | None] = []

        def ensure_dir(self, *_args, **_kwargs) -> None:
            return None

        def upload_tree(self, *_args, **_kwargs) -> None:
            return None

        def remove_tree(self, *_args, **_kwargs) -> None:
            return None

        def upload_file(
            self,
            local_path,
            remote_path,
            mode=None,
            transaction=None,
        ) -> None:
            self.modes.append(mode)
            if transaction is not None:
                self.transactional_files.append(remote_path)

        def upload_text(
            self,
            content,
            remote_path,
            mode=None,
            transaction=None,
        ) -> None:
            self.modes.append(mode)
            if transaction is not None:
                self.transactional_files.append(remote_path)

        def atomic_replace_tree(self, staging: str, destination: str):
            return module.DeploymentReplacement(
                destination,
                f'{destination}.previous-test',
                True,
            )

    remote = RecordingRemote()
    transaction = module.DeploymentTransaction(remote)
    private_key = tmp_path / 'AuthKey.p8'
    certificate = tmp_path / 'AppleRootCA.cer'

    module.upload_artifacts(remote, REPO_ROOT, '/root/ASapptaro', transaction)
    module.upload_apple_credentials(remote, private_key, [certificate], transaction)
    module.upload_runtime_envs(
        remote,
        '/root/ASapptaro',
        'BACKEND=value\n',
        'ADMIN=value\n',
        transaction,
    )

    assert set(remote.transactional_files) == {
        '/root/ASapptaro/docker-compose.yml',
        '/root/ASapptaro/secrets/apple/AuthKey.p8',
        '/root/ASapptaro/.env.backend',
        '/root/ASapptaro/.env.admin',
    }
    assert remote.modes
    assert all(mode == 0o600 for mode in remote.modes)


def test_tree_replacements_keep_backups_until_commit_and_restore_on_rollback(
    tmp_path: Path,
) -> None:
    module = _load_deploy_module()

    class LocalTreeRemote:
        def atomic_replace_tree(self, staging: str, destination: str):
            staged = Path(staging)
            target = Path(destination)
            backup = target.with_name(f'{target.name}.previous-test')
            had_previous = target.exists()
            if had_previous:
                target.rename(backup)
            staged.rename(target)
            return module.TreeReplacement(
                destination=str(target),
                backup=str(backup),
                had_previous=had_previous,
            )

        def commit_replacement(self, replacement) -> None:
            backup = Path(replacement.backup)
            if backup.exists():
                shutil.rmtree(backup)

        def rollback_replacement(self, replacement) -> None:
            target = Path(replacement.destination)
            backup = Path(replacement.backup)
            if target.exists():
                shutil.rmtree(target)
            if replacement.had_previous:
                backup.rename(target)

    target = tmp_path / 'templates'
    target.mkdir()
    (target / 'version.txt').write_text('old', encoding='utf-8')
    staged = tmp_path / 'templates.staging'
    staged.mkdir()
    (staged / 'version.txt').write_text('new', encoding='utf-8')

    transaction = module.TreeDeploymentTransaction(LocalTreeRemote())
    replacement = transaction.replace_tree(str(staged), str(target))

    assert (target / 'version.txt').read_text(encoding='utf-8') == 'new'
    assert Path(replacement.backup, 'version.txt').read_text(encoding='utf-8') == 'old'

    transaction.rollback()

    assert (target / 'version.txt').read_text(encoding='utf-8') == 'old'
    assert not Path(replacement.backup).exists()

    staged.mkdir()
    (staged / 'version.txt').write_text('final', encoding='utf-8')
    transaction = module.TreeDeploymentTransaction(LocalTreeRemote())
    replacement = transaction.replace_tree(str(staged), str(target))
    transaction.commit()

    assert (target / 'version.txt').read_text(encoding='utf-8') == 'final'
    assert not Path(replacement.backup).exists()


def test_failed_post_swap_step_restores_tree_and_restarts_previous_stack(
    tmp_path: Path,
) -> None:
    module = _load_deploy_module()

    class LocalTreeRemote:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def atomic_replace_tree(self, staging: str, destination: str):
            staged = Path(staging)
            target = Path(destination)
            backup = target.with_name(f'{target.name}.previous-test')
            target.rename(backup)
            staged.rename(target)
            return module.TreeReplacement(str(target), str(backup), True)

        def commit_replacement(self, replacement) -> None:
            shutil.rmtree(replacement.backup)

        def rollback_replacement(self, replacement) -> None:
            shutil.rmtree(replacement.destination)
            Path(replacement.backup).rename(replacement.destination)

        def run(self, command: str, check: bool = True):
            self.commands.append(command)
            if 'ps --format json' in command:
                return 0, '\n'.join(
                    (
                        '{"Service":"asapptaro_backend","State":"running",'
                        '"Health":"healthy"}',
                        '{"Service":"asapptaro_admin_bot","State":"running",'
                        '"Health":"healthy"}',
                    )
                ), ''
            return 0, '', ''

    target = tmp_path / 'tarot'
    target.mkdir()
    (target / 'version.txt').write_text('old', encoding='utf-8')
    staged = tmp_path / 'tarot.staging'
    staged.mkdir()
    (staged / 'version.txt').write_text('new', encoding='utf-8')
    remote = LocalTreeRemote()

    with pytest.raises(RuntimeError, match='post-swap failure'):
        with module.transactional_tree_deployment(
            remote,
            '/root/ASapptaro',
            health_timeout_seconds=1,
        ) as transaction:
            replacement = transaction.replace_tree(str(staged), str(target))
            assert Path(replacement.backup).is_dir()
            raise RuntimeError('post-swap failure')

    assert (target / 'version.txt').read_text(encoding='utf-8') == 'old'
    assert not Path(replacement.backup).exists()
    assert any('up -d --build --remove-orphans' in command for command in remote.commands)
    assert any('ps --format json' in command for command in remote.commands)


def test_mixed_file_and_tree_transaction_restores_full_previous_release_before_restart(
    tmp_path: Path,
) -> None:
    module = _load_deploy_module()

    class LocalMixedRemote:
        def __init__(self, tracked_paths: list[Path]) -> None:
            self.tracked_paths = tracked_paths
            self.restart_snapshots: list[dict[str, str]] = []

        def _replace(self, staging: str, destination: str):
            staged = Path(staging)
            target = Path(destination)
            backup = target.with_name(f'{target.name}.previous-test')
            had_previous = target.exists()
            if had_previous:
                target.rename(backup)
            staged.rename(target)
            return module.DeploymentReplacement(
                destination=str(target),
                backup=str(backup),
                had_previous=had_previous,
            )

        def atomic_replace_tree(self, staging: str, destination: str):
            return self._replace(staging, destination)

        def atomic_replace_file(self, staging: str, destination: str):
            return self._replace(staging, destination)

        def commit_replacement(self, replacement) -> None:
            backup = Path(replacement.backup)
            if backup.is_dir():
                shutil.rmtree(backup)
            elif backup.exists():
                backup.unlink()

        def rollback_replacement(self, replacement) -> None:
            target = Path(replacement.destination)
            backup = Path(replacement.backup)
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            if replacement.had_previous:
                backup.rename(target)

        def run(self, command: str, check: bool = True):
            if 'up -d --build --remove-orphans' in command:
                self.restart_snapshots.append(
                    {
                        path.name: (
                            (path / 'version.txt').read_text(encoding='utf-8')
                            if path.is_dir()
                            else path.read_text(encoding='utf-8')
                        )
                        for path in self.tracked_paths
                    }
                )
            if 'ps --format json' in command:
                return 0, '\n'.join(
                    (
                        '{"Service":"asapptaro_backend","State":"running",'
                        '"Health":"healthy"}',
                        '{"Service":"asapptaro_admin_bot","State":"running",'
                        '"Health":"healthy"}',
                    )
                ), ''
            return 0, '', ''

    target_tree = tmp_path / 'templates'
    target_tree.mkdir()
    (target_tree / 'version.txt').write_text('old-tree', encoding='utf-8')
    target_files = [
        tmp_path / 'docker-compose.yml',
        tmp_path / 'AuthKey.p8',
        tmp_path / '.env.backend',
        tmp_path / '.env.admin',
    ]
    for path in target_files:
        path.write_text(f'old-{path.name}', encoding='utf-8')
    tracked_paths = [target_tree, *target_files]
    remote = LocalMixedRemote(tracked_paths)

    with pytest.raises(RuntimeError, match='health failure'):
        with module.transactional_tree_deployment(
            remote,
            '/root/ASapptaro',
            health_timeout_seconds=1,
        ) as transaction:
            staged_tree = tmp_path / 'templates.staging'
            staged_tree.mkdir()
            (staged_tree / 'version.txt').write_text('new-tree', encoding='utf-8')
            replacements = [transaction.replace_tree(str(staged_tree), str(target_tree))]
            for target in target_files:
                staged = target.with_name(f'{target.name}.staging')
                staged.write_text(f'new-{target.name}', encoding='utf-8')
                replacements.append(transaction.replace_file(str(staged), str(target)))
            assert all(Path(item.backup).exists() for item in replacements)
            raise RuntimeError('health failure')

    assert remote.restart_snapshots == [
        {
            'templates': 'old-tree',
            'docker-compose.yml': 'old-docker-compose.yml',
            'AuthKey.p8': 'old-AuthKey.p8',
            '.env.backend': 'old-.env.backend',
            '.env.admin': 'old-.env.admin',
        }
    ]
    assert all(not Path(item.backup).exists() for item in replacements)

    with module.transactional_tree_deployment(
        remote,
        '/root/ASapptaro',
        health_timeout_seconds=1,
    ) as transaction:
        staged_tree = tmp_path / 'templates.final'
        staged_tree.mkdir()
        (staged_tree / 'version.txt').write_text('final-tree', encoding='utf-8')
        committed = [transaction.replace_tree(str(staged_tree), str(target_tree))]
        for target in target_files:
            staged = target.with_name(f'{target.name}.final')
            staged.write_text(f'final-{target.name}', encoding='utf-8')
            committed.append(transaction.replace_file(str(staged), str(target)))
        assert all(Path(item.backup).exists() for item in committed)

    assert (target_tree / 'version.txt').read_text(encoding='utf-8') == 'final-tree'
    assert all(
        target.read_text(encoding='utf-8') == f'final-{target.name}'
        for target in target_files
    )
    assert all(not Path(item.backup).exists() for item in committed)


def test_remote_host_rejects_unknown_ssh_host_keys() -> None:
    raw = SCRIPT_PATH.read_text(encoding='utf-8')

    assert 'RejectPolicy' in raw
    assert 'AutoAddPolicy' not in raw


def test_remote_run_drains_both_streams_before_exit_status() -> None:
    module = _load_deploy_module()

    class FakeChannel:
        def __init__(self) -> None:
            self.stdout = [b'out']
            self.stderr = [b'err']

        def recv_ready(self) -> bool:
            return bool(self.stdout)

        def recv(self, _size: int) -> bytes:
            return self.stdout.pop(0)

        def recv_stderr_ready(self) -> bool:
            return bool(self.stderr)

        def recv_stderr(self, _size: int) -> bytes:
            return self.stderr.pop(0)

        def exit_status_ready(self) -> bool:
            return not self.stdout and not self.stderr

        def recv_exit_status(self) -> int:
            assert self.exit_status_ready(), 'streams were not drained'
            return 0

    channel = FakeChannel()
    stream = type('Stream', (), {'channel': channel})()
    remote = object.__new__(module.RemoteHost)
    remote._client = type(
        'Client',
        (),
        {'exec_command': lambda self, command, timeout: (None, stream, stream)},
    )()

    exit_code, out, err = remote.run('docker compose up')

    assert exit_code == 0
    assert out == 'out'
    assert err == 'err'


def test_remote_run_times_out_and_closes_hung_channel() -> None:
    module = _load_deploy_module()

    class HungChannel:
        closed = False

        def recv_ready(self) -> bool:
            return False

        def recv_stderr_ready(self) -> bool:
            return False

        def exit_status_ready(self) -> bool:
            return False

        def close(self) -> None:
            self.closed = True

    channel = HungChannel()
    stream = type('Stream', (), {'channel': channel})()
    remote = object.__new__(module.RemoteHost)
    remote._command_timeout_seconds = 0.01
    remote._client = type(
        'Client',
        (),
        {'exec_command': lambda self, command, timeout: (None, stream, stream)},
    )()

    with pytest.raises(TimeoutError, match='timed out'):
        remote.run('hung command')

    assert channel.closed is True


def test_https_health_redirect_handler_rejects_downgrade() -> None:
    module = _load_deploy_module()
    handler = module.HTTPSOnlyRedirectHandler()
    request = urllib.request.Request('https://api.example.com/v1/health')

    with pytest.raises(urllib.error.HTTPError, match='non-HTTPS'):
        handler.redirect_request(
            request,
            None,
            302,
            'Found',
            {},
            'http://api.example.com/v1/health',
        )


def test_external_health_rejects_non_https_final_url(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_deploy_module()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def geturl(self) -> str:
            return 'http://api.example.com/v1/health'

        def read(self) -> bytes:
            return (
                b'{"status":"ok","service":"ASapptaro Backend",'
                b'"environment":"production"}'
            )

    class Opener:
        def open(self, request, timeout):
            return Response()

    monotonic_values = iter((0.0, 0.0, 2.0))
    monkeypatch.setattr(module.urllib.request, 'build_opener', lambda *_handlers: Opener())
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(monotonic_values))
    monkeypatch.setattr(module.time, 'sleep', lambda _seconds: None)

    with pytest.raises(RuntimeError, match='Production health URL must use HTTPS'):
        module.wait_for_external_health(
            'https://api.example.com/v1/health',
            timeout_seconds=1,
        )


def test_compose_status_requires_both_services_running_and_healthy() -> None:
    module = _load_deploy_module()
    healthy = '\n'.join(
        (
            '{"Service":"asapptaro_backend","State":"running","Health":"healthy"}',
            '{"Service":"asapptaro_admin_bot","State":"running","Health":"healthy"}',
        )
    )
    module.validate_compose_status(healthy)

    unhealthy = healthy.replace(
        '"Service":"asapptaro_admin_bot","State":"running","Health":"healthy"',
        '"Service":"asapptaro_admin_bot","State":"exited","Health":"unhealthy"',
    )
    with pytest.raises(RuntimeError, match='asapptaro_admin_bot'):
        module.validate_compose_status(unhealthy)


def test_compose_status_can_validate_backend_only_mode() -> None:
    module = _load_deploy_module()
    backend_only = (
        '{"Service":"asapptaro_backend","State":"running","Health":"healthy"}'
    )

    module.validate_compose_status(
        backend_only,
        required_services=(module.BACKEND_SERVICE_NAME,),
    )


def test_backend_only_compose_up_targets_only_backend_service() -> None:
    module = _load_deploy_module()

    command = module.build_compose_up_command(
        '/root/ASapptaro',
        required_services=(module.BACKEND_SERVICE_NAME,),
    )

    assert 'stop asapptaro_admin_bot' in command
    assert 'rm -f asapptaro_admin_bot' in command
    assert command.endswith('--force-recreate asapptaro_backend')


def test_forward_and_rollback_compose_up_force_container_recreation() -> None:
    module = _load_deploy_module()
    healthy = '\n'.join(
        (
            '{"Service":"asapptaro_backend","State":"running","Health":"healthy"}',
            '{"Service":"asapptaro_admin_bot","State":"running","Health":"healthy"}',
        )
    )

    class FakeRemote:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def run(self, command: str, check: bool = True):
            self.commands.append(command)
            if 'ps --format json' in command:
                return 0, healthy, ''
            return 0, '', ''

    class FakeTransaction:
        def __init__(self) -> None:
            self.rolled_back = False

        def rollback(self) -> None:
            self.rolled_back = True

    remote = FakeRemote()
    transaction = FakeTransaction()

    module.restart_stack(remote, '/root/ASapptaro')
    module.rollback_deployment(
        remote,
        '/root/ASapptaro',
        transaction,
        health_timeout_seconds=1,
    )

    compose_up_commands = [
        command
        for command in remote.commands
        if 'up -d --build --remove-orphans' in command
    ]
    assert transaction.rolled_back is True
    assert len(compose_up_commands) == 2
    assert all('--force-recreate' in command for command in compose_up_commands)


def test_database_backup_is_timestamped_and_precedes_compose_restart() -> None:
    module = _load_deploy_module()

    class FakeRemote:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def run(self, command: str, check: bool = True):
            self.commands.append(command)
            return 0, '', ''

    remote = FakeRemote()
    timestamp = datetime(2026, 7, 18, 12, 34, 56, tzinfo=UTC)
    module.restart_stack(remote, '/root/ASapptaro', timestamp=timestamp)

    assert 'asapptaro.db.20260718T123456Z.bak' in remote.commands[0]
    assert 'sqlite3' in remote.commands[0]
    assert (
        'docker compose --project-name asapptaro --file docker-compose.yml '
        'up -d --build --remove-orphans'
    ) in remote.commands[1]


def test_local_validation_checks_all_release_assets_without_network() -> None:
    module = _load_deploy_module()

    summary = module.validate_local_assets(REPO_ROOT)

    assert summary['remote_dir'] == '/root/ASapptaro'
    assert summary['host_port'] == 8023
    assert summary['services'] == ['asapptaro_backend', 'asapptaro_admin_bot']


def test_release_files_do_not_embed_private_keys_or_tokens() -> None:
    raw = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in (COMPOSE_PATH, SCRIPT_PATH, RUNBOOK_PATH)
    )

    assert '-----BEGIN PRIVATE KEY-----' not in raw
    assert re.search(r'\b\d{9,12}:AA[A-Za-z0-9_-]{20,}\b', raw) is None


def test_apple_env_example_documents_required_keys_without_legacy_billing() -> None:
    raw = APPLE_ENV_EXAMPLE_PATH.read_text(encoding='utf-8')

    for key in (
        'APP_STORE_APPLE_ID=',
        'APP_STORE_KEY_ID=',
        'APP_STORE_ISSUER_ID=',
        'APP_STORE_PRIVATE_KEY_LOCAL_FILE=',
        'APP_STORE_ROOT_CERTIFICATES_LOCAL_DIR=',
        'ADMIN_BOT_TOKEN=',
        'ADMIN_IDS=',
    ):
        assert key in raw
    assert 'YOOKASSA_' not in raw
    assert 'GOOGLE_PLAY_' not in raw


def test_standalone_local_readiness_check_succeeds_without_network() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT_PATH), '--local-only'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert 'asapptaro_backend' in result.stdout
    assert 'network_actions' in result.stdout
