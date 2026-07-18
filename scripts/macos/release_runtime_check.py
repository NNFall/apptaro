#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Sequence


MINIMUM_PYTHON = (3, 11)


class RuntimeCheckError(RuntimeError):
    pass


def validate_python_version(version: tuple[int, int]) -> None:
    if version < MINIMUM_PYTHON:
        actual = '.'.join(str(part) for part in version)
        required = '.'.join(str(part) for part in MINIMUM_PYTHON)
        raise RuntimeCheckError(
            f'Python {required} or newer is required by the backend runtime; found {actual}.',
        )


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        validate_python_version((sys.version_info.major, sys.version_info.minor))
    except RuntimeCheckError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print(f'Python runtime accepted: {sys.version_info.major}.{sys.version_info.minor}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
