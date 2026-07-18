from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_PATH = REPO_ROOT / 'scripts' / 'macos' / 'release_runtime_check.py'


def _load_check() -> ModuleType:
    spec = importlib.util.spec_from_file_location('release_runtime_check', CHECK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_check()


@pytest.mark.parametrize('version', [(3, 11), (3, 12), (4, 0)])
def test_supported_python_versions_are_accepted(version: tuple[int, int]) -> None:
    check.validate_python_version(version)


@pytest.mark.parametrize('version', [(3, 10), (3, 9), (2, 7)])
def test_python_below_311_is_rejected(version: tuple[int, int]) -> None:
    with pytest.raises(check.RuntimeCheckError, match='3.11'):
        check.validate_python_version(version)
