from __future__ import annotations

from typing import Iterable

from config import load_config
from services.logger import get_logger

logger = get_logger()


def _unique(ids: Iterable[int]) -> list[int]:
    seen = set()
    out = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


async def notify_admins(bot, text: str) -> None:
    try:
        cfg = load_config()
        if not cfg.admin_ids:
            return
        for admin_id in _unique(cfg.admin_ids):
            try:
                await bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        logger.exception('Admin notify failed')
