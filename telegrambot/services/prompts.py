from __future__ import annotations

from typing import List


def title_prompt(topic: str) -> str:
    return (
        'Сформируй короткое название презентации (3–7 слов).  из запроса пользователя, по максимуму в соответствии с запросом пользователя '
        'Без кавычек, без точки в конце, только текст.\n'
        f'Тема: {topic}\n'
    )


def outline_prompt(topic: str, slides: int) -> str:
    return (
        'Составь план презентации. Верни только список заголовков слайдов, '
        'по одному на строку, без нумерации.\n'
        f'Тема: {topic}\n'
        f'Количество слайдов: {slides}\n'
    )


def outline_comment_prompt(topic: str, slides: int, outline: List[str], comment: str) -> str:
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


def slides_prompt(topic: str, outline: List[str]) -> str:
    return (
        'Сгенерируй JSON-массив слайдов. Каждый элемент: '
        '{"title": str, "text": str, "image_prompt": str}. '
        'Текст должен быть кратким (2-3 предложения), не длиннее 320 символов. '
        'Заголовок 4-7 слов. '
        'Возвращай только JSON.\n'
        f'Тема: {topic}\n'
        f'План: {outline}\n'
    )
