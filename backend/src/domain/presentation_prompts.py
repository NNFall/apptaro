from __future__ import annotations

import re


# Platform prompts that are kept from the shell architecture.
def title_prompt(topic: str, language: str = 'en') -> str:
    if language == 'en':
        return (
            'Create a short tarot reading title in English, 3-7 words. '
            'No quotes, no final period, text only.\n'
            f'User question: {topic}\n'
        )
    return (
        'Сформулируй короткое название таро-расклада (3-7 слов) из вопроса пользователя. '
        'Без кавычек, без точки в конце, только текст.\n'
        f'Вопрос: {topic}\n'
    )


def outline_prompt(topic: str, slides: int, language: str = 'en') -> str:
    if language == 'en':
        return (
            'Create a short outline for a tarot-style reading. Return only one title per line, '
            'without numbering.\n'
            f'User question: {topic}\n'
            f'Number of items: {slides}\n'
        )
    return (
        'Составь короткий план таро-расклада. Верни только список заголовков позиций, '
        'по одному на строку, без нумерации.\n'
        f'Вопрос пользователя: {topic}\n'
        f'Количество позиций: {slides}\n'
    )


def outline_comment_prompt(
    topic: str,
    slides: int,
    outline: list[str],
    comment: str,
    language: str = 'en',
) -> str:
    outline_text = '\n'.join(f'- {item}' for item in outline)
    if language == 'en':
        return (
            'You have the current tarot reading outline and a user comment. '
            'Regenerate the outline with the requested number of items. '
            'Return only one title per line, without numbering.\n'
            f'User question: {topic}\n'
            f'Number of items: {slides}\n'
            f'Current outline:\n{outline_text}\n'
            f'User comment: {comment}\n'
        )
    return (
        'У тебя есть текущий план таро-расклада и комментарий пользователя. '
        'Перегенерируй план из указанного количества позиций с учетом комментария. '
        'Верни только список заголовков, по одному на строку, без нумерации.\n'
        f'Вопрос пользователя: {topic}\n'
        f'Количество позиций: {slides}\n'
        f'Текущий план:\n{outline_text}\n'
        f'Комментарий пользователя: {comment}\n'
    )


def slides_prompt(topic: str, outline: list[str], language: str = 'en') -> str:
    if language == 'en':
        return (
            'Generate a JSON array. Each item must be: '
            '{"title": str, "text": str, "image_prompt": str}. '
            'Text should be short, 2-3 sentences, no longer than 320 characters. '
            'Title should be 4-7 words. Return JSON only.\n'
            f'User question: {topic}\n'
            f'Outline: {outline}\n'
        )
    return (
        'Сгенерируй JSON-массив слайдов. Каждый элемент: '
        '{"title": str, "text": str, "image_prompt": str}. '
        'Текст краткий (2-3 предложения), не длиннее 320 символов. '
        'Заголовок 4-7 слов. Возвращай только JSON.\n'
        f'Тема: {topic}\n'
        f'План: {outline}\n'
    )


# Tarot prompts synchronized with telegram_taro_bot/prompts/tarot_prompts.py
# and extended with stricter card-binding constraints.
def teaser_intro_text(question: str, language: str = 'en') -> str:
    if language == 'en':
        return (
            f'🔮 <b>You asked:</b>\n'
            f'"{question}"\n\n'
            'Let us see what the cards are saying.'
        )
    return (
        f'🔮 <b>Ты спросил:</b>\n'
        f'«{question}»\n\n'
        'Давайте посмотрим, что говорят карты.'
    )


def paywall_text(language: str = 'en') -> str:
    if language == 'en':
        return 'To open the full reading, choose a subscription.'
    return 'Чтобы открыть полный расклад, оформите подписку.'


def confirmation_text(language: str = 'en') -> str:
    if language == 'en':
        return 'Ask your question and I will draw the cards.'
    return 'Задайте свой вопрос — я сразу открою карты.'


def system_prompt(mode: str, language: str = 'en') -> str:
    if language == 'en':
        common = (
            'You are an experienced tarot reader. Answer only in English. '
            'Return the answer strictly in Telegram legacy Markdown: only *bold*, _italic_, and `mono` are allowed. '
            'Do not use HTML tags or Markdown headings like ##. '
            'Start with: "Let us see what the cards are saying:". '
            'Before interpreting the cards, give 2-3 introductory sentences tied to the user question. '
            'Use only the cards and orientations provided in the user request. '
            'Do not replace cards, add new cards, or change orientations.'
        )
        safety = (
            ' If the question touches pregnancy, health, death, legal, or medical topics, '
            'do not make direct predictions. Reframe it gently as emotional state, relationships, resources, or support.'
        )
        if mode == 'teaser':
            return (
                common
                + ' This is trial mode: reveal only the first card. Do not reveal cards 2 or 3. '
                'Structure: intro, one block for the first card, short conclusion, and a soft call to unlock the full reading.'
                + safety
            )
        if mode == 'followup':
            return (
                common
                + ' This is a follow-up question about a previous reading. Briefly connect to the prior answer, then answer the follow-up. '
                'Do not repeat the whole previous reading.'
                + safety
            )
        if mode == 'continuation':
            return (
                common
                + ' This is a continuation: the first card has already been revealed and explained. '
                'Connect briefly to the first answer, interpret positions 2 and 3, then give a final conclusion. '
                'Do not retell the first card in full. '
                'Format exactly as: intro, "*2) <card name>* - <meaning>", "*3) <card name>* - <meaning>", then "*Summary:* ...".'
                + safety
            )
        return (
            common
            + ' This is a full three-card reading. Structure: intro, three position blocks, final summary. '
            + safety
        )

    common = (
        'Ты эксперт-таролог. Отвечай только на русском языке. '
        'Верни ответ строго в Telegram Markdown (legacy): допустимы только *жирный*, _курсив_ и `моно`. '
        'Не используй HTML-теги и markdown заголовки типа ##. '
        'Начинай ответ фразой: "Давайте посмотрим, что говорят карты:". '
        'Перед разбором карт дай 2-3 предложения вступления в контексте вопроса. '
        'Используй только карты и ориентации, переданные в пользовательском запросе. '
        'Запрещено подменять карты, добавлять новые карты или менять ориентацию.'
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
        'Сформируй разбор только первой карты и обязательно связуй смысл карты с вопросом. '
        'Не упоминай 2-ю и 3-ю карты. '
        f'Используй в разборе только эту карту: {first_card_line}. '
        'Не заменяй ее на другую карту и не меняй ориентацию. '
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
        'Разрешено использовать только карты и ориентации из блока "Карты". '
        'Не подменяй названия карт и не добавляй новые. '
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


def _english_followup_user_prompt(
    question: str,
    followup: str,
    cards_block: str,
    last_answer: str,
    mode: str,
) -> str:
    return (
        f'Original question: {question}\n\n'
        f'User follow-up: {followup}\n\n'
        f'Available cards:\n{cards_block}\n\n'
        f'Previous answer:\n{last_answer}\n\n'
        f'Mode: {mode}\n\n'
        'If mode is teaser, do not reveal cards 2 or 3. '
        'Give a clear clarification and a short practical takeaway.'
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
        'Продолжи разбор: краткая связка с первым ответом, затем отдельные блоки по 2-й и 3-й карте. '
        'Используй только карты из блока "Новые карты", не добавляй и не подменяй карты. '
        'Формат:\n'
        '*2) <название карты>* — <2-4 предложения в контексте вопроса>\n'
        '*3) <название карты>* — <2-4 предложения в контексте вопроса>\n'
        '*Итог:* <1-2 предложения>.'
    )


def _english_teaser_user_prompt(question: str, first_card_line: str) -> str:
    return (
        f'User question: {question}\n\n'
        'Reading positions:\n'
        '1) current situation around the question\n'
        '2) key obstacle or knot\n'
        '3) advice and direction\n\n'
        f'Revealed card: {first_card_line}\n\n'
        'Interpret only the first card and connect it clearly to the user question. '
        'Do not mention cards 2 or 3. Do not replace the card or change its orientation. '
        'End with a short call to unlock the full reading.'
    )


def _english_full_user_prompt(question: str, cards_block: str) -> str:
    return (
        f'User question: {question}\n\n'
        'Reading positions:\n'
        '1) current situation around the question\n'
        '2) key obstacle or knot\n'
        '3) advice and direction\n\n'
        f'Cards:\n{cards_block}\n\n'
        'Give a detailed interpretation of each position and a final summary. '
        'Explain every card in the context of the question. '
        'Use only the cards and orientations from the Cards block. '
        'Do not replace card names and do not add new cards. '
        'Phrase predictions as tendencies, not absolute guarantees.'
    )


def _english_continuation_user_prompt(
    question: str,
    first_card_line: str,
    first_text: str,
    cards_block: str,
) -> str:
    return (
        f'Original question: {question}\n\n'
        f'First card already revealed: {first_card_line}\n\n'
        f'Previous answer about the first card:\n{first_text}\n\n'
        'Reading positions:\n'
        '2) key obstacle or knot\n'
        '3) advice and direction\n\n'
        f'New cards:\n{cards_block}\n\n'
        'Continue the reading: briefly connect to the first answer, then interpret cards 2 and 3 separately. '
        'Use only the cards from the New cards block. Do not add or replace cards.\n'
        'Format:\n'
        '*2) <card name>* - <2-4 sentences in the context of the question>\n'
        '*3) <card name>* - <2-4 sentences in the context of the question>\n'
        '*Summary:* <1-2 sentences>.'
    )


def tarot_reading_prompt(question: str, cards_block: str, *, mode: str = 'auto', language: str = 'en') -> str:
    resolved_mode = _resolve_mode(mode, cards_block)
    first_card_line = _first_card_line(cards_block)
    if language == 'en':
        if resolved_mode == 'teaser':
            user_prompt = _english_teaser_user_prompt(question, first_card_line)
        else:
            user_prompt = _english_full_user_prompt(question, cards_block)
        return (
            f'SYSTEM INSTRUCTIONS:\n{system_prompt(resolved_mode, language=language)}\n\n'
            f'USER REQUEST:\n{user_prompt}'
        )

    if resolved_mode == 'teaser':
        user_prompt = teaser_user_prompt(question, first_card_line)
    else:
        user_prompt = full_user_prompt(question, cards_block)
    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt(resolved_mode, language="ru")}\n\n'
        f'ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_prompt}'
    )


def tarot_followup_prompt(
    question: str,
    followup: str,
    cards_block: str,
    last_answer: str,
    mode: str,
    language: str = 'en',
) -> str:
    if language == 'en':
        return (
            f'SYSTEM INSTRUCTIONS:\n{system_prompt("followup", language=language)}\n\n'
            'USER REQUEST:\n'
            f'{_english_followup_user_prompt(question, followup, cards_block, last_answer, mode)}'
        )

    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt("followup", language="ru")}\n\n'
        'ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n'
        f'{followup_user_prompt(question, followup, cards_block, last_answer, mode)}'
    )


def tarot_continuation_prompt(
    question: str,
    first_card_line: str,
    first_text: str,
    cards_block: str,
    language: str = 'en',
) -> str:
    if language == 'en':
        return (
            f'SYSTEM INSTRUCTIONS:\n{system_prompt("continuation", language=language)}\n\n'
            'USER REQUEST:\n'
            f'{_english_continuation_user_prompt(question, first_card_line, first_text, cards_block)}'
        )

    return (
        f'СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt("continuation", language="ru")}\n\n'
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
        return '1) card is not defined'
    first = re.sub(r'^\s*\d+[\).]?\s*', '', lines[0]).strip()
    return first or lines[0]
