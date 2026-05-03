from __future__ import annotations

import logging


def configure_logging(level: str = 'INFO') -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        force=True,
    )
    # httpx INFO logs include full request URLs, which can expose Telegram bot tokens.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
