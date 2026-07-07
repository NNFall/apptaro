from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiogram.exceptions import TelegramConflictError
from aiogram.methods import GetUpdates

from telegram_admin_bot.main import _poll_updates


class _ConflictBot:
    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> None:
        _ = drop_pending_updates

    async def get_updates(self, **_: object) -> list[object]:
        raise TelegramConflictError(
            method=GetUpdates(),
            message='Conflict: terminated by other getUpdates request',
        )


class _Dispatcher:
    def resolve_used_update_types(self) -> list[str]:
        return []


class AdminBotPollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflict_error_logs_actionable_duplicate_token_message(self) -> None:
        async def stop_after_log(_: int) -> None:
            raise asyncio.CancelledError

        with tempfile.TemporaryDirectory() as temp_dir:
            config = SimpleNamespace(
                heartbeat_path=Path(temp_dir) / 'admin_bot.heartbeat',
                polling_timeout_seconds=1,
                polling_retry_max_seconds=1,
            )

            with patch('telegram_admin_bot.main.asyncio.sleep', stop_after_log):
                with self.assertLogs('telegram_admin_bot.main', level='ERROR') as logs:
                    with self.assertRaises(asyncio.CancelledError):
                        await _poll_updates(_ConflictBot(), _Dispatcher(), config)

        self.assertIn('another getUpdates polling process', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
