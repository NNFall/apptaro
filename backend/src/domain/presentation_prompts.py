from __future__ import annotations

import re


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


def tarot_reading_prompt(question: str, cards_block: str, *, mode: str = 'auto') -> str:
    resolved_mode = _resolve_mode(mode, cards_block)
    if resolved_mode == 'teaser':
        user_prompt = _teaser_user_prompt(question, cards_block)
    else:
        user_prompt = _full_user_prompt(question, cards_block)
    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{_system_prompt(resolved_mode)}\n\n'
        f'ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_prompt}'
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


def _resolve_mode(mode: str, cards_block: str) -> str:
    if mode in {'teaser', 'full'}:
        return mode
    return 'teaser' if _cards_count(cards_block) <= 1 else 'full'


def _cards_count(cards_block: str) -> int:
    lines = [line.strip() for line in cards_block.splitlines() if line.strip()]
    return len(lines)


def _system_prompt(mode: str) -> str:
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
        'не давай прямых предсказаний. Мягко предложи безопасный ракурс '
        '(эмоциональное состояние, отношения, ресурс, поддержка) и продолжи расклад в этом ключе.'
    )
    if mode == 'teaser':
        return (
            common
            + ' Это триал-режим: раскрывай только первую карту. '
            'Не раскрывай 2-ю и 3-ю карту, но мягко усили мотивацию открыть полный расклад. '
            'Структура: вступление, 1 блок по первой карте, короткий вывод и CTA. '
            + safety
        )
    return (
        common
        + ' Это полный расклад из трех карт. '
        'Структура: вступление, 3 блока по позициям, финальное резюме. '
        + safety
    )


def _teaser_user_prompt(question: str, cards_block: str) -> str:
    first_card_line = _first_card_line(cards_block)
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


def _full_user_prompt(question: str, cards_block: str) -> str:
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


def _first_card_line(cards_block: str) -> str:
    lines = [line.strip() for line in cards_block.splitlines() if line.strip()]
    if not lines:
        return '1) карта не определена'
    first = re.sub(r'^\s*\d+[\).]?\s*', '', lines[0]).strip()
    return first or lines[0]
