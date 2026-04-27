import logging
import os
from collections import deque
from typing import Deque


class LastLinesFileHandler(logging.Handler):
    def __init__(self, path: str, max_lines: int = 1000, encoding: str = 'utf-8') -> None:
        super().__init__()
        self.path = path
        self.max_lines = max_lines
        self.encoding = encoding
        self._lines: Deque[str] = deque(maxlen=max_lines)
        self._load_existing()

    def _load_existing(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding=self.encoding) as f:
                for line in f:
                    self._lines.append(line.rstrip('\n'))
        except OSError:
            return

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._lines.append(msg)
        try:
            with open(self.path, 'w', encoding=self.encoding) as f:
                f.write('\n'.join(self._lines))
                f.write('\n')
        except OSError:
            pass


_logger = None


def setup_logger(log_file: str, max_lines: int = 1000) -> logging.Logger:
    global _logger
    if _logger:
        return _logger

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logger = logging.getLogger('slides_bot')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    file_handler = LastLinesFileHandler(log_file, max_lines=max_lines)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return logging.getLogger('slides_bot')
    return _logger
