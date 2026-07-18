from __future__ import annotations

import sys
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.integrations.admin_notifier import AdminNotifier  # noqa: E402


class CapturingNotifier(AdminNotifier):
    def __init__(self) -> None:
        super().__init__(bot_token="", admin_ids=[])
        self.messages: list[str] = []

    async def notify(self, text: str) -> None:
        self.messages.append(text)

    async def _notify(self, text: str, *, propagate_errors: bool) -> None:
        self.messages.append(text)


class FakeTelegramResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request('POST', 'https://api.telegram.org/test')
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError('telegram rejected message', request=request, response=response)


class FakeAsyncClient:
    outcome: object = FakeTelegramResponse(200)

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args, **kwargs):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class PerRecipientFakeAsyncClient:
    status_by_chat_id: dict[str, int] = {}
    attempted_chat_ids: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        type(self).attempted_chat_ids = []
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args, **kwargs):
        chat_id = str(kwargs['json']['chat_id'])
        type(self).attempted_chat_ids.append(chat_id)
        return FakeTelegramResponse(type(self).status_by_chat_id[chat_id])


class AdminNotifierFormattingTests(unittest.IsolatedAsyncioTestCase):
    async def test_reliable_telegram_error_never_exposes_bot_token(self) -> None:
        token = 'super-secret-telegram-token'
        notifier = AdminNotifier(bot_token=token, admin_ids=['123'])
        request = httpx.Request(
            'POST',
            f'https://api.telegram.org/bot{token}/sendMessage',
        )
        FakeAsyncClient.outcome = httpx.Response(500, request=request)

        with patch('src.integrations.admin_notifier.httpx.AsyncClient', FakeAsyncClient):
            with self.assertRaises(httpx.HTTPStatusError) as captured:
                await notifier.notify_app_store_event(
                    event_type='renewal',
                    client_id='client-123',
                    product_id='weekly_readings',
                    transaction_id='tx-1',
                    notification_uuid='uuid-1',
                    detail='DID_RENEW',
                )

        rendered = ''.join(
            traceback.format_exception(
                type(captured.exception),
                captured.exception,
                captured.exception.__traceback__,
            )
        )
        self.assertNotIn(token, str(captured.exception))
        self.assertNotIn(token, rendered)
        self.assertIsNone(captured.exception.__context__)

    async def test_best_effort_telegram_log_never_exposes_bot_token(self) -> None:
        token = 'super-secret-telegram-token'
        notifier = AdminNotifier(bot_token=token, admin_ids=['123'])
        request = httpx.Request(
            'POST',
            f'https://api.telegram.org/bot{token}/sendMessage',
        )
        FakeAsyncClient.outcome = httpx.ConnectError(
            f'connection failed for bot{token}',
            request=request,
        )

        with patch('src.integrations.admin_notifier.httpx.AsyncClient', FakeAsyncClient):
            with self.assertLogs('src.integrations.admin_notifier', level='ERROR') as logs:
                await notifier.notify('legacy notification')

        self.assertNotIn(token, '\n'.join(logs.output))

    async def test_best_effort_continues_after_per_recipient_failure(self) -> None:
        notifier = AdminNotifier(bot_token='secret-token', admin_ids=['admin-1', 'admin-2'])
        PerRecipientFakeAsyncClient.status_by_chat_id = {
            'admin-1': 500,
            'admin-2': 200,
        }

        with patch(
            'src.integrations.admin_notifier.httpx.AsyncClient',
            PerRecipientFakeAsyncClient,
        ):
            with self.assertLogs('src.integrations.admin_notifier', level='ERROR') as logs:
                await notifier.notify('legacy notification')

        self.assertEqual(
            PerRecipientFakeAsyncClient.attempted_chat_ids,
            ['admin-1', 'admin-2'],
        )
        self.assertEqual(len(logs.output), 1)
        self.assertIn('admin-1', logs.output[0])
        self.assertNotIn('secret-token', logs.output[0])

    async def test_app_store_event_requires_bot_token_and_admin_recipient(self) -> None:
        for notifier in (
            AdminNotifier(bot_token='', admin_ids=['123']),
            AdminNotifier(bot_token='token', admin_ids=[]),
            AdminNotifier(bot_token='', admin_ids=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, 'not configured'):
                await notifier.notify_app_store_event(
                    event_type='purchase',
                    client_id='client-123',
                    product_id='weekly_readings',
                    transaction_id='tx-1',
                    notification_uuid='uuid-1',
                    detail='SUBSCRIBED',
                )

    async def test_app_store_event_propagates_telegram_429_and_5xx(self) -> None:
        notifier = AdminNotifier(bot_token='token', admin_ids=['123'])
        with patch('src.integrations.admin_notifier.httpx.AsyncClient', FakeAsyncClient):
            for status_code in (429, 500):
                FakeAsyncClient.outcome = FakeTelegramResponse(status_code)
                with self.assertRaises(httpx.HTTPStatusError):
                    await notifier.notify_app_store_event(
                        event_type='renewal',
                        client_id='client-123',
                        product_id='weekly_readings',
                        transaction_id='tx-1',
                        notification_uuid='uuid-1',
                        detail='DID_RENEW',
                    )

    async def test_app_store_event_propagates_telegram_network_error(self) -> None:
        notifier = AdminNotifier(bot_token='token', admin_ids=['123'])
        request = httpx.Request('POST', 'https://api.telegram.org/test')
        FakeAsyncClient.outcome = httpx.ConnectError('offline', request=request)
        with patch('src.integrations.admin_notifier.httpx.AsyncClient', FakeAsyncClient):
            with self.assertRaises(httpx.ConnectError):
                await notifier.notify_app_store_event(
                    event_type='renewal',
                    client_id='client-123',
                    product_id='weekly_readings',
                    transaction_id='tx-1',
                    notification_uuid='uuid-1',
                    detail='DID_RENEW',
                )

    async def test_app_store_lifecycle_event_format_has_no_secrets(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_app_store_event(
            event_type="renewal",
            client_id="client-1234567890abcdef",
            product_id="weekly_readings",
            transaction_id="2000000123456789",
            notification_uuid="uuid-renewal",
            detail="DID_RENEW/BILLING_RECOVERY",
        )
        self.assertEqual(
            notifier.messages[-1],
            "<b>App Store renewal</b>\n"
            "<b>User ID:</b> <code>client-1234…abcdef</code>\n"
            "<b>Product ID:</b> <code>weekly_readings</code>\n"
            "<b>Transaction ID:</b> <code>2000000123456789</code>\n"
            "<b>Event:</b> DID_RENEW/BILLING_RECOVERY",
        )

    async def test_app_store_validation_failure_is_concise(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_app_store_event(
            event_type="validation_failure",
            client_id="",
            product_id="",
            transaction_id="",
            notification_uuid="",
            detail="signature verification failed",
        )
        self.assertEqual(
            notifier.messages[-1],
            "<b>App Store validation failure</b>\n"
            "<b>Event:</b> signature verification failed",
        )

    async def test_new_client_message_uses_short_id_and_bold(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_new_client("appslides_monhlids_f677777d2d08d0e059", "без метки")
        self.assertEqual(
            notifier.messages[-1],
            "<b>👤 Новый пользователь</b>\n"
            "<b>User ID:</b> <code>appslides_m…d0e059</code>\n"
            "<b>Метка:</b> без метки",
        )

    async def test_outline_created_message_uses_html(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_outline_created(
            "appslides_monhlids_f677777d2d08d0e059",
            "тема откуда берутся страхи титульный лист учреждения: Краснодарский краевой базовый медицинский колледж",
            3,
        )
        self.assertIn("<b>🔮 Расклад подготовлен</b>", notifier.messages[-1])
        self.assertIn("<b>User ID:</b> <code>appslides_m…d0e059</code>", notifier.messages[-1])
        self.assertIn("<b>Вопрос:</b> тема откуда берутся страхи", notifier.messages[-1])
        self.assertIn("<b>Карт:</b> 3", notifier.messages[-1])

    async def test_google_play_purchase_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_google_play_purchase(
            client_id="client-1234567890abcdef",
            plan_key="monthly",
            plan_title="Monthly Subscription",
            tokens=50,
            product_id="monthly_subscription_50",
            order_id="GPA.1234-5678-9012-34567",
            restored=False,
        )
        self.assertEqual(
            notifier.messages[-1],
            "<b>Google Play purchase</b>\n"
            "<b>User ID:</b> <code>client-1234…abcdef</code>\n"
            "<b>Тариф:</b> monthly (Monthly Subscription - 50 раскладов)\n"
            "<b>Product ID:</b> <code>monthly_subscription_50</code>\n"
            "<b>Order ID:</b> <code>GPA.1234-5678-9012-34567</code>",
        )

    async def test_promo_redeemed_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_promo_redeemed(
            client_id="client-123",
            promo_code="abc123",
            tokens=10,
        )
        self.assertEqual(
            notifier.messages[-1],
            "<b>🎁 Промокод активирован</b>\n"
            "<b>User ID:</b> <code>client-123</code>\n"
            "<b>Промокод:</b> <code>ABC123</code>\n"
            "<b>Начислено раскладов:</b> 10",
        )

    async def test_auto_renew_success_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_auto_renew_success(
            client_id="client-1234567890abcdef",
            plan_key="week",
            plan_title="Неделя",
            tokens=10,
            amount_rub=199,
            status="succeeded",
            payment_id="payment-1",
        )
        self.assertEqual(
            notifier.messages[-1],
            "<b>Автосписание - УСПЕХ</b>\n"
            "<b>User ID:</b> <code>client-1234…abcdef</code>\n"
            "<b>Тариф:</b> week (Неделя - 10 раскладов)\n"
            "<b>Сумма:</b> 199₽\n"
            "<b>Status:</b> succeeded\n"
            "<b>Payment ID:</b> <code>payment-1</code>",
        )

    async def test_auto_renew_error_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_auto_renew_error(
            client_id="client-123",
            plan_key="week",
            plan_title="Неделя",
            tokens=10,
            amount_rub=199,
            status="error",
            payment_id="-",
            reason="payment_method_id отсутствует",
            expires_subscription=True,
        )
        self.assertIn("<b>Автосписание - ОШИБКА</b>", notifier.messages[-1])
        self.assertIn("<b>User ID:</b> <code>client-123</code>", notifier.messages[-1])
        self.assertIn("<b>Причина:</b> payment_method_id отсутствует", notifier.messages[-1])
        self.assertIn("<b>Следующая попытка:</b> не будет", notifier.messages[-1])

    async def test_manual_renew_success_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_renewal_success(
            client_id="client-123",
            plan_key="month",
            plan_title="Месяц",
            tokens=50,
            amount_rub=499,
            status="succeeded",
            payment_id="payment-2",
        )
        self.assertEqual(
            notifier.messages[-1],
            "<b>Продление подписки - УСПЕХ</b>\n"
            "<b>User ID:</b> <code>client-123</code>\n"
            "<b>Тариф:</b> month (Месяц - 50 раскладов)\n"
            "<b>Сумма:</b> 499₽\n"
            "<b>Status:</b> succeeded\n"
            "<b>Payment ID:</b> <code>payment-2</code>",
        )


if __name__ == "__main__":
    unittest.main()
