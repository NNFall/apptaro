from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='📊 Создать презентацию', callback_data='menu:gen')],
            [InlineKeyboardButton(text='📄 PDF → DOCX', callback_data='menu:pdf2docx')],
            [InlineKeyboardButton(text='📄 DOCX → PDF', callback_data='menu:docx2pdf')],
            [InlineKeyboardButton(text='📊 PPTX → PDF', callback_data='menu:pptx2pdf')],
            [InlineKeyboardButton(text='💳 Баланс / Подписка', callback_data='menu:plan')],
            [InlineKeyboardButton(text='❓ Помощь', callback_data='menu:help')],
        ]
    )


def main_menu_button_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu:main')]]
    )


def subscription_actions_kb(
    show_renew_now: bool = False,
    show_cancel: bool = False,
) -> InlineKeyboardMarkup:
    rows = []
    if show_renew_now:
        rows.append([InlineKeyboardButton(text='🔄 Обновить подписку сейчас', callback_data='renew:now')])
    if show_cancel:
        rows.append([InlineKeyboardButton(text='❌ Отключить подписку', callback_data='sub:cancel')])
    rows.append([InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu:main')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def slides_count_kb() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=str(i), callback_data=f'slides:{i}')
        for i in range(4, 11)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def outline_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='✅ Принять план', callback_data='outline:ok'),
                InlineKeyboardButton(text='✍️ Редактировать', callback_data='outline:edit'),
            ],
            [InlineKeyboardButton(text='⬅ Отмена', callback_data='outline:cancel')],
        ]
    )


def outline_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='⬅ Отмена', callback_data='outline:cancel')]]
    )


def outline_error_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔄 Перегенерировать', callback_data='outline:regen')],
            [InlineKeyboardButton(text='⬅ Отмена', callback_data='outline:cancel')],
        ]
    )


def design_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Шаблон 1', callback_data='design:1')],
            [InlineKeyboardButton(text='Шаблон 2', callback_data='design:2')],
            [InlineKeyboardButton(text='Шаблон 3', callback_data='design:3')],
            [InlineKeyboardButton(text='Шаблон 4', callback_data='design:4')],
        ]
    )


def payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✅ Выбрать подписку', callback_data='plan:choose')],
        ]
    )


def payment_options_kb(options: list[tuple[str, str]], back_data: str = 'plan:back') -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=text, callback_data=data)] for text, data in options]
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=back_data)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_url_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='💳 Оплатить', url=url)],
            [InlineKeyboardButton(text='🏠 Меню', callback_data='menu:main')],
        ]
    )


def mailer_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='📊 Создать презентацию', callback_data='menu:gen')],
        ]
    )
