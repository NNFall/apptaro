from __future__ import annotations

import unittest

from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.integrations.admin_notifier import AdminNotifier  # noqa: E402


class CapturingNotifier(AdminNotifier):
    def __init__(self) -> None:
        super().__init__(bot_token='', admin_ids=[])
        self.messages: list[str] = []

    async def notify(self, text: str) -> None:
        self.messages.append(text)


class AdminNotifierFormattingTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_renew_success_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_auto_renew_success(
            client_id='client-123',
            plan_key='week',
            plan_title='Неделя',
            tokens=10,
            amount_rub=199,
            status='succeeded',
            payment_id='payment-1',
        )
        self.assertEqual(
            notifier.messages[-1],
            'Автосписание - УСПЕХ\n'
            'User ID: client-123\n'
            'Тариф: week (Неделя - 10 генераций)\n'
            'Сумма: 199₽\n'
            'Status: succeeded\n'
            'Payment ID: payment-1',
        )

    async def test_auto_renew_error_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_auto_renew_error(
            client_id='client-123',
            plan_key='week',
            plan_title='Неделя',
            tokens=10,
            amount_rub=199,
            status='error',
            payment_id='-',
            reason='payment_method_id отсутствует',
            expires_subscription=True,
        )
        self.assertIn('Автосписание - ОШИБКА', notifier.messages[-1])
        self.assertIn('User ID: client-123', notifier.messages[-1])
        self.assertIn('Причина: payment_method_id отсутствует', notifier.messages[-1])
        self.assertIn('Следующая попытка: не будет', notifier.messages[-1])

    async def test_manual_renew_success_format(self) -> None:
        notifier = CapturingNotifier()
        await notifier.notify_renewal_success(
            client_id='client-123',
            plan_key='month',
            plan_title='Месяц',
            tokens=50,
            amount_rub=499,
            status='succeeded',
            payment_id='payment-2',
        )
        self.assertEqual(
            notifier.messages[-1],
            'Продление подписки - УСПЕХ\n'
            'User ID: client-123\n'
            'Тариф: month (Месяц - 50 генераций)\n'
            'Сумма: 499₽\n'
            'Status: succeeded\n'
            'Payment ID: payment-2',
        )


if __name__ == '__main__':
    unittest.main()
