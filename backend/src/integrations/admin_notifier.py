from __future__ import annotations

import html
import logging
from datetime import datetime
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


def _shorten_text(value: str, max_len: int = 120) -> str:
    cleaned = " ".join((value or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _dt_short(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "-"
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return raw


def _display_client_id(client_id: str) -> str:
    value = (client_id or "").strip()
    if len(value) <= 22:
        return value
    return f"{value[:11]}…{value[-6:]}"


def _code(value: str) -> str:
    return f"<code>{html.escape(value)}</code>"


def _bold(value: str) -> str:
    return f"<b>{html.escape(value)}</b>"


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

        api_url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        timeout = httpx.Timeout(10.0, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                for admin_id in self._admin_ids:
                    try:
                        await client.post(
                            api_url,
                            json={
                                "chat_id": admin_id,
                                "text": text,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True,
                            },
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception("Failed to send admin notification to %s", admin_id)
        except Exception:  # noqa: BLE001
            logger.exception("Admin notify failed")

    async def notify_new_client(self, client_id: str, tag: str = "без метки") -> None:
        await self.notify(
            f"{_bold('👤 Новый пользователь')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Метка:')} {html.escape(tag)}"
        )

    async def notify_outline_created(self, client_id: str, topic: str, slides: int) -> None:
        await self.notify(
            f"{_bold('🔮 Расклад подготовлен')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Вопрос:')} {html.escape(_shorten_text(topic))}\n"
            f"{_bold('Карт:')} {slides}"
        )

    async def notify_outline_updated(self, client_id: str, topic: str, slides: int) -> None:
        await self.notify(
            f"{_bold('🔄 Карты перетянуты по комментарию')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Вопрос:')} {html.escape(_shorten_text(topic))}\n"
            f"{_bold('Карт:')} {slides}"
        )

    async def notify_text_error(self, client_id: str, error: str) -> None:
        await self.notify(
            f"{_bold('❌ Ошибка Kie.ai')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Причина:')} {html.escape(error)}"
        )

    async def notify_payment_success(self, client_id: str, plan_title: str) -> None:
        await self.notify(
            f"{_bold('💰 Успешная покупка (YooKassa)')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Тариф:')} {html.escape(plan_title)}"
        )

    async def notify_promo_redeemed(self, *, client_id: str, promo_code: str, tokens: int) -> None:
        await self.notify(
            f"{_bold('🎁 Промокод активирован')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Промокод:')} {_code((promo_code or '').strip().upper())}\n"
            f"{_bold('Начислено раскладов:')} {tokens}"
        )

    async def notify_subscription_canceled(self, client_id: str) -> None:
        await self.notify(
            f"{_bold('❌ Подписка отключена')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}"
        )

    async def notify_generation_success(self, client_id: str) -> None:
        await self.notify(
            f"{_bold('✅ Успешный расклад таро')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}"
        )

    async def notify_generation_failed(self, client_id: str, error: str) -> None:
        await self.notify(
            f"{_bold('❌ Ошибка генерации')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Причина:')} {html.escape(error)}"
        )

    async def notify_conversion_success(self, client_id: str, source_ext: str, target_ext: str) -> None:
        await self.notify(
            f"{_bold('✅ Конвертация выполнена')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Формат:')} {html.escape(source_ext)}→{html.escape(target_ext)}"
        )

    async def notify_conversion_failed(
        self,
        client_id: str,
        source_ext: str,
        target_ext: str,
        error: str,
    ) -> None:
        await self.notify(
            f"{_bold('❌ Ошибка конвертации')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Формат:')} {html.escape(source_ext)}→{html.escape(target_ext)}\n"
            f"{_bold('Причина:')} {html.escape(error)}"
        )

    async def notify_renewal_success(
        self,
        *,
        client_id: str,
        plan_key: str,
        plan_title: str,
        tokens: int,
        amount_rub: int,
        status: str,
        payment_id: str,
    ) -> None:
        await self.notify(
            f"{_bold('Продление подписки - УСПЕХ')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Тариф:')} {html.escape(plan_key)} ({html.escape(plan_title)} - {tokens} раскладов)\n"
            f"{_bold('Сумма:')} {amount_rub}₽\n"
            f"{_bold('Status:')} {html.escape(status)}\n"
            f"{_bold('Payment ID:')} {_code(payment_id or '-')}"
        )

    async def notify_renewal_error(
        self,
        *,
        client_id: str,
        plan_key: str,
        plan_title: str,
        tokens: int,
        amount_rub: int,
        status: str,
        payment_id: str,
        reason: str,
    ) -> None:
        await self.notify(
            f"{_bold('Продление подписки - ОШИБКА')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Тариф:')} {html.escape(plan_key)} ({html.escape(plan_title)} - {tokens} раскладов)\n"
            f"{_bold('Сумма:')} {amount_rub}₽\n"
            f"{_bold('Status:')} {html.escape(status)}\n"
            f"{_bold('Payment ID:')} {_code(payment_id or '-')}\n"
            f"{_bold('Причина:')} {html.escape(reason)}"
        )

    async def notify_auto_renew_success(
        self,
        *,
        client_id: str,
        plan_key: str,
        plan_title: str,
        tokens: int,
        amount_rub: int,
        status: str,
        payment_id: str,
    ) -> None:
        await self.notify(
            f"{_bold('Автосписание - УСПЕХ')}\n"
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}\n"
            f"{_bold('Тариф:')} {html.escape(plan_key)} ({html.escape(plan_title)} - {tokens} раскладов)\n"
            f"{_bold('Сумма:')} {amount_rub}₽\n"
            f"{_bold('Status:')} {html.escape(status)}\n"
            f"{_bold('Payment ID:')} {_code(payment_id or '-')}"
        )

    async def notify_auto_renew_error(
        self,
        *,
        client_id: str,
        plan_key: str,
        plan_title: str,
        tokens: int,
        amount_rub: int,
        status: str,
        payment_id: str,
        reason: str,
        next_try: str | None = None,
        expires_subscription: bool = False,
    ) -> None:
        lines = [
            _bold("Автосписание - ОШИБКА"),
            f"{_bold('User ID:')} {_code(_display_client_id(client_id))}",
            f"{_bold('Тариф:')} {html.escape(plan_key)} ({html.escape(plan_title)} - {tokens} раскладов)",
            f"{_bold('Сумма:')} {amount_rub}₽",
            f"{_bold('Status:')} {html.escape(status)}",
            f"{_bold('Payment ID:')} {_code(payment_id or '-')}",
            f"{_bold('Причина:')} {html.escape(reason)}",
        ]
        if expires_subscription:
            lines.append(f"{_bold('Следующая попытка:')} не будет (подписка переведена в expired)")
        elif next_try:
            lines.append(f"{_bold('Следующая попытка:')} {html.escape(_dt_short(next_try))}")
        await self.notify("\n".join(lines))
