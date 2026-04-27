from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Создать презентацию')],
            [KeyboardButton(text='PDF в DOCX'), KeyboardButton(text='DOCX в PDF')],
            [KeyboardButton(text='PPTX в PDF')],
            [KeyboardButton(text='Мой тариф')],
        ],
        resize_keyboard=True,
    )
