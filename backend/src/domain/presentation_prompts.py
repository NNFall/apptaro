from __future__ import annotations

import re


# Presentation-generation prompts kept from the platform shell.
def title_prompt(topic: str) -> str:
    return (
        'Сформулируй короткое название таро-расклада (3-7 слов) из вопроса пользователя. '
        'Без кавычек, без точки в конце, только текст.\n'
        f'Вопрос: {topic}\n'
    )


def outline_prompt(topic: str, slides: int) -> str:
    return (
        'Составь план презентации. Верни только список заголовков слайдов, '
        'по одному на строку, без нумерации.\n'
        f'Тема: {topic}\n'
        f'Количество слайдов: {slides}\n'
    )


def outline_comment_prompt(topic: str, slides: int, outline: list[str], comment: str) -> str:
    outline_text = '\n'.join(f'- {item}' for item in outline)
    return (
        'У тебя есть текущий план презентации и комментарий пользователя. '
        'Перегенерируй план из указанного количества слайдов с учетом комментария. '
        'Верни только список заголовков, по одному на строку, без нумерации.\n'
        f'Тема: {topic}\n'
        f'Количество слайдов: {slides}\n'
        f'Текущий план:\n{outline_text}\n'
        f'Комментарий пользователя: {comment}\n'
    )


def slides_prompt(topic: str, outline: list[str]) -> str:
    return (
        'Сгенерируй JSON-массив слайдов. Каждый элемент: '
        '{"title": str, "text": str, "image_prompt": str}. '
        'Текст должен быть кратким (2-3 предложения), не длиннее 320 символов. '
        'Заголовок 4-7 слов. '
        'Возвращай только JSON.\n'
        f'Тема: {topic}\n'
        f'План: {outline}\n'
    )


# Tarot prompts synchronized with telegram_taro_bot/prompts/tarot_prompts.py.
def teaser_intro_text(question: str) -> str:
    return (
        f'🔮 <b>Ты спросил:</b>\n'
        f'«{question}»\n\n'
        'Давайте посмотрим, что говорят карты.'
    )


def paywall_text() -> str:
    return 'Чтобы открыть полный расклад, оформите подписку.'


def confirmation_text() -> str:
    return 'Задайте свой вопрос — я сразу открою карты.'


def system_prompt(mode: str) -> str:
    common = (
        'Ты эксперт-таролог. Отвечай только на русском языке. '
        'Верни ответ строго в Telegram Markdown (legacy): '
        'допустимы только *жирный*, _курсив_ и `моно`. '
        'Не используй HTML-теги и markdown заголовки типа ##. '
        'Начинай ответ фразой: "Давайте посмотрим, что говорят карты:". '
        'Перед разбором карт дай 2-3 предложения вступления в контексте вопроса.'
    )
    safety = (
        'Если вопрос про беременность, здоровье, смерть, юридические или медицинские темы, '
        'не давай прямых предсказаний. Мягко предложи безопасный ракурс (эмоциональное состояние, '
        'отношения, ресурс, поддержка) и продолжи расклад в этом ключе.'
    )
    if mode == 'teaser':
        return (
            common
            + ' Это триал-режим: раскрывай только первую карту. '
            'Не раскрывай 2-ю и 3-ю карту, но мягко усили мотивацию открыть полный расклад. '
            'Структура: вступление, 1 блок по первой карте, короткий вывод и CTA. '
            + safety
        )
    if mode == 'followup':
        return (
            common
            + ' Это уточняющий вопрос по предыдущему раскладу. '
            'Сначала коротко напомни суть ответа в 1-2 предложениях, затем ответь на уточнение. '
            'Не повторяй полный текст расклада. '
            + safety
        )
    if mode == 'continuation':
        return (
            common
            + ' Это продолжение расклада: первая карта уже раскрыта и объяснена. '
            'Сделай связку с первым ответом, разберись по 2-й и 3-й позициям и дай финальный вывод. '
            'Не пересказывай полностью первую карту. '
            'Формат строго: вступление 1-2 предложения, затем блоки '
            '"*2) <название карты>* — <смысл в контексте вопроса>", '
            '"*3) <название карты>* — <смысл в контексте вопроса>", '
            'в конце "*Итог:* ...". '
            + safety
        )
    return (
        common
        + ' Это полный расклад из трех карт. '
        'Структура: вступление, 3 блока по позициям, финальное резюме. '
        + safety
    )


def teaser_user_prompt(question: str, first_card_line: str) -> str:
    return (
        f'Вопрос пользователя: {question}\n\n'
        'Позиции расклада:\n'
        '1) текущая ситуация вокруг вопроса\n'
        '2) ключевое препятствие или узел\n'
        '3) совет и направление\n\n'
        f'Открытая карта: {first_card_line}\n\n'
        'Сформируй разбор только первой карты и обязательно связывай смысл карты с вопросом. '
        'Не упоминай 2-ю и 3-ю карты. '
        'В конце добавь короткий CTA на полный расклад.'
    )


def full_user_prompt(question: str, cards_block: str) -> str:
    return (
        f'Вопрос пользователя: {question}\n\n'
        'Позиции расклада:\n'
        '1) текущая ситуация вокруг вопроса\n'
        '2) ключевое препятствие или узел\n'
        '3) совет и направление\n\n'
        f'Карты:\n{cards_block}\n\n'
        'Дай подробный разбор каждой позиции и итог. '
        'Каждую карту объясняй в контексте вопроса. '
        'Прогнозы формулируй вероятностно, без абсолютных обещаний.'
    )


def followup_user_prompt(
    question: str,
    followup: str,
    cards_block: str,
    last_answer: str,
    mode: str,
) -> str:
    return (
        f'Исходный вопрос: {question}\n\n'
        f'Уточнение пользователя: {followup}\n\n'
        f'Доступные карты:\n{cards_block}\n\n'
        f'Предыдущий ответ:\n{last_answer}\n\n'
        f'Режим: {mode}\n\n'
        'Если режим teaser, не раскрывай 2-ю и 3-ю карты. '
        'Дай понятное уточнение и небольшой практичный вывод.'
    )


def continuation_user_prompt(
    question: str,
    first_card_line: str,
    first_text: str,
    cards_block: str,
) -> str:
    return (
        f'Исходный вопрос: {question}\n\n'
        f'Первая карта уже раскрыта: {first_card_line}\n\n'
        f'Предыдущий ответ по первой карте:\n{first_text}\n\n'
        'Позиции расклада:\n'
        '2) ключевое препятствие или узел\n'
        '3) совет и направление\n\n'
        f'Новые карты:\n{cards_block}\n\n'
        'Продолжи разбор: краткая связка с первым ответом, затем отдельные блоки по 2-й и 3-й карте '
        'в формате:\n'
        '*2) <название карты>* — <2-4 предложения в контексте вопроса>\n'
        '*3) <название карты>* — <2-4 предложения в контексте вопроса>\n'
        '*Итог:* <1-2 предложения>.'
    )


def tarot_reading_prompt(question: str, cards_block: str, *, mode: str = 'auto') -> str:
    resolved_mode = _resolve_mode(mode, cards_block)
    first_card_line = _first_card_line(cards_block)
    if resolved_mode == 'teaser':
        user_prompt = teaser_user_prompt(question, first_card_line)
    else:
        user_prompt = full_user_prompt(question, cards_block)
    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt(resolved_mode)}\n\n'
        f'ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_prompt}'
    )


def tarot_followup_prompt(
    question: str,
    followup: str,
    cards_block: str,
    last_answer: str,
    mode: str,
) -> str:
    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt("followup")}\n\n'
        'ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n'
        f'{followup_user_prompt(question, followup, cards_block, last_answer, mode)}'
    )


def tarot_continuation_prompt(
    question: str,
    first_card_line: str,
    first_text: str,
    cards_block: str,
) -> str:
    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt("continuation")}\n\n'
        'ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n'
        f'{continuation_user_prompt(question, first_card_line, first_text, cards_block)}'
    )


def _resolve_mode(mode: str, cards_block: str) -> str:
    if mode in {'teaser', 'full', 'followup', 'continuation'}:
        return mode
    return 'teaser' if _cards_count(cards_block) <= 1 else 'full'


def _cards_count(cards_block: str) -> int:
    lines = [line.strip() for line in cards_block.splitlines() if line.strip()]
    return len(lines)


def _first_card_line(cards_block: str) -> str:
    lines = [line.strip() for line in cards_block.splitlines() if line.strip()]
    if not lines:
        return '1) карта не определена'
    first = re.sub(r'^\s*\d+[\).]?\s*', '', lines[0]).strip()
    return first or lines[0]
