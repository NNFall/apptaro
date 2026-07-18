from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = REPO_ROOT / 'scripts' / 'deploy' / 'deploy_asapptaro_remote.py'


def _load_deploy_module():
    spec = importlib.util.spec_from_file_location(
        'deploy_asapptaro_remote',
        DEPLOY_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load deployment module: {DEPLOY_SCRIPT}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Check local ASapptaro App Store deployment readiness.',
    )
    parser.add_argument('--local-only', action='store_true', required=True)
    parser.parse_args()

    deploy = _load_deploy_module()
    summary = deploy.validate_local_assets(REPO_ROOT)
    print(
        json.dumps(
            {**summary, 'network_actions': False},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
