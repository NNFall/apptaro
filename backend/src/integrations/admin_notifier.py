from __future__ import annotations

import logging
from typing import Iterable

import httpx


logger = logging.getLogger(__name__)


def _unique(ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in ids:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class AdminNotifier:
    def __init__(self, *, bot_token: str, admin_ids: list[str]) -> None:
        self._bot_token = bot_token.strip()
        self._admin_ids = _unique(admin_ids)

    @property
    def enabled(self) -> bool:
        return bool(self._bot_token and self._admin_ids)

    async def notify(self, text: str) -> None:
        if not self.enabled:
            return

        api_url = f'https://api.telegram.org/bot{self._bot_token}/sendMessage'
        timeout = httpx.Timeout(10.0, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                for admin_id in self._admin_ids:
                    try:
                        await client.post(
                            api_url,
                            json={
                                'chat_id': admin_id,
                                'text': text,
                            },
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception('Failed to send admin notification to %s', admin_id)
        except Exception:  # noqa: BLE001
            logger.exception('Admin notify failed')

    async def notify_new_client(self, client_id: str, tag: str = 'без метки') -> None:
        await self.notify(f'👤 Новый пользователь: {client_id}, метка: {tag}')

    async def notify_outline_created(self, client_id: str, topic: str, slides: int) -> None:
        await self.notify(
            f'🧠 План создан: пользователь {client_id} тема "{_shorten_text(topic)}", слайдов {slides}'
        )

    async def notify_outline_updated(self, client_id: str, topic: str, slides: int) -> None:
        await self.notify(
            f'✍️ План обновлен по комментарию: пользователь {client_id} '
            f'тема "{_shorten_text(topic)}", слайдов {slides}'
        )

    async def notify_text_error(self, client_id: str, error: str) -> None:
        await self.notify(f'❌ Ошибка Kie.ai: {error} (client {client_id})')

    async def notify_payment_success(self, client_id: str, plan_title: str) -> None:
        await self.notify(f'💰 Успешная покупка (ЮKassa). Пользователь {client_id}, тариф {plan_title}')

    async def notify_subscription_canceled(self, client_id: str) -> None:
        await self.notify(f'❌ Отключил подписку. Пользователь {client_id}')

    async def notify_generation_success(self, client_id: str) -> None:
        await self.notify(f'✅ Успешная генерация (Презентация). Пользователь {client_id}')

    async def notify_generation_failed(self, client_id: str, error: str) -> None:
        await self.notify(f'❌ Ошибка генерации: {error} (client {client_id})')

    async def notify_conversion_success(self, client_id: str, source_ext: str, target_ext: str) -> None:
        await self.notify(f'✅ Конвертация выполнена ({source_ext}→{target_ext}). Пользователь {client_id}')

    async def notify_conversion_failed(
        self,
        client_id: str,
        source_ext: str,
        target_ext: str,
        error: str,
    ) -> None:
        await self.notify(
            f'❌ Ошибка конвертации ({source_ext}→{target_ext}): {error} (client {client_id})'
        )


def _shorten_text(value: str, max_len: int = 120) -> str:
    cleaned = ' '.join((value or '').split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + '…'
