from typing import Optional

_storage = None


def set_storage(storage) -> None:
    global _storage
    _storage = storage


def get_storage() -> Optional[object]:
    return _storage
