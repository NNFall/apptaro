from __future__ import annotations

import sys
import unittest
from pathlib import Path


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


class AdminNotifierFormattingTests(unittest.IsolatedAsyncioTestCase):
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
