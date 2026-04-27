import asyncio
import os
import uuid
from typing import List

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.types.input_file import FSInputFile

from config import load_config, PLANS
from database.models import get_subscription_for_use, decrement_subscription, log_generation
from keyboards.inline import (
    slides_count_kb,
    outline_actions_kb,
    outline_error_kb,
    outline_edit_kb,
    design_kb,
    payment_options_kb,
    main_menu_button_kb,
    main_menu_kb,
)
from services.kie_api import KieClient, KieError
from services.pptx_builder import build_presentation
from services.converter import convert_file
from services.logger import get_logger
from services.admin_notify import notify_admins

router = Router()
config = load_config()
logger = get_logger()
kie_client = KieClient(
    api_key=config.kie_api_key,
    base_url=config.kie_base_url,
    text_model=config.kie_text_model,
    image_model=config.kie_image_model,
    text_endpoint=config.kie_text_endpoint,
    text_fallback_models=config.kie_text_fallback_models,
    replicate_api_token=config.replicate_api_token,
    replicate_base_url=config.replicate_base_url,
    replicate_model=config.replicate_model,
    replicate_wait_seconds=config.replicate_wait_seconds,
    replicate_poll_interval=config.replicate_poll_interval,
    replicate_timeout_seconds=config.replicate_timeout_seconds,
    replicate_default_input=config.replicate_default_input,
    replicate_text_model=config.replicate_text_model,
    replicate_text_prompt_field=config.replicate_text_prompt_field,
    replicate_text_default_input=config.replicate_text_default_input,
)


class PresentationStates(StatesGroup):
    waiting_topic = State()
    waiting_slide_count = State()
    waiting_outline_confirm = State()
    waiting_outline_edit = State()
    waiting_design = State()
    waiting_payment = State()


@router.callback_query(F.data == 'menu:gen')
async def start_presentation_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = callback.from_user
    logger.info('Menu click: create presentation user=%s username=%s', user.id, user.username)
    await _start_presentation_flow(callback.message, state)


@router.message(F.text == 'Создать презентацию')
async def start_presentation(message: Message, state: FSMContext) -> None:
    user = message.from_user
    logger.info('Text command: create presentation user=%s username=%s', user.id, user.username)
    await _start_presentation_flow(message, state)


@router.message(Command('presentation'))
async def start_presentation_cmd(message: Message, state: FSMContext) -> None:
    user = message.from_user
    logger.info('Command: presentation user=%s username=%s', user.id, user.username)
    await _start_presentation_flow(message, state)


async def _start_presentation_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PresentationStates.waiting_topic)
    await message.answer(
        'Напиши тему презентации и пожелания ✍️\n'
        'Например: «Удивительные факты о космосе, для школьников»'
    )


@router.message(PresentationStates.waiting_topic)
async def handle_topic(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer('Пришлите тему текстом ✍️')
        return
    topic = message.text.strip()
    if not topic:
        await message.answer('Тема не должна быть пустой 🙏 Попробуй еще раз.')
        return
    logger.info('Topic received: user=%s topic_len=%s', message.from_user.id, len(topic))
    await state.update_data(topic=topic)
    await state.set_state(PresentationStates.waiting_slide_count)
    await message.answer('Сколько слайдов нужно? 📑', reply_markup=slides_count_kb())


@router.callback_query(F.data.startswith('slides:'))
async def handle_slide_count(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    slides_total = int(callback.data.split(':', 1)[1])
    content_slides = max(1, slides_total - 1)
    data = await state.get_data()
    topic = data.get('topic', '')
    logger.info('Slides count выбран: user=%s slides=%s', callback.from_user.id, slides_total)
    await state.update_data(slides_total=slides_total, slides=content_slides)
    await callback.message.answer('Формирую план... 🧠')
    try:
        title, outline = await asyncio.gather(
            kie_client.generate_title(topic),
            kie_client.generate_outline(topic, content_slides),
        )
    except KieError as exc:
        logger.warning('Outline failed: user=%s err=%s', callback.from_user.id, exc)
        await notify_admins(
            callback.message.bot,
            f'❌ Ошибка Kie.ai: {exc} (user {callback.from_user.id} @{callback.from_user.username or "-"})',
        )
        await state.update_data(outline=[], slides=content_slides)
        await state.set_state(PresentationStates.waiting_outline_confirm)
        await callback.message.answer(
            f'Не удалось получить план 😢\n{exc}\nНажми «Перегенерировать».',
            reply_markup=outline_error_kb(),
        )
        return
    await state.update_data(outline=outline, title=title)
    await state.set_state(PresentationStates.waiting_outline_confirm)
    logger.info(
        'Outline generated: user=%s slides=%s topic="%s"',
        callback.from_user.id,
        content_slides,
        _shorten_text(topic),
    )
    await notify_admins(
        callback.message.bot,
        f'🧠 План создан: пользователь {callback.from_user.id} (@{callback.from_user.username or "-"}) '
        f'тема "{_shorten_text(topic)}", слайдов {content_slides}',
    )
    text = _format_outline(outline, title)
    await callback.message.answer(text, parse_mode='HTML')
    await callback.message.answer(
        'Принять или изменить?\n'
        'Можно написать комментарий к плану, и я его обновлю.',
        reply_markup=outline_actions_kb(),
    )


@router.callback_query(F.data == 'outline:regen')
async def handle_outline_regen(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    logger.info('Outline regenerate: user=%s', callback.from_user.id)
    await callback.message.answer('Начал перегенерацию плана... 🔄 Подожди немного.')
    data = await state.get_data()
    topic = data.get('topic', '')
    content_slides = data.get('slides', 6)
    try:
        outline = await kie_client.generate_outline(topic, content_slides)
    except KieError as exc:
        logger.warning('Outline regenerate failed: user=%s err=%s', callback.from_user.id, exc)
        await notify_admins(
            callback.message.bot,
            f'❌ Ошибка Kie.ai: {exc} (user {callback.from_user.id} @{callback.from_user.username or "-"})',
        )
        await callback.message.answer(f'Не удалось получить план 😢\n{exc}')
        return
    title = data.get('title') or topic
    await state.update_data(outline=outline)
    logger.info(
        'Outline regenerated: user=%s slides=%s topic="%s"',
        callback.from_user.id,
        content_slides,
        _shorten_text(topic),
    )
    await notify_admins(
        callback.message.bot,
        f'🔄 План перегенерирован: пользователь {callback.from_user.id} (@{callback.from_user.username or "-"}) '
        f'тема "{_shorten_text(topic)}", слайдов {content_slides}',
    )
    text = _format_outline(outline, title)
    await callback.message.answer(text, parse_mode='HTML')
    await callback.message.answer(
        'Принять или изменить?\n'
        'Можно написать комментарий к плану, и я его обновлю.',
        reply_markup=outline_actions_kb(),
    )


@router.callback_query(F.data == 'outline:edit')
async def handle_outline_edit_request(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    logger.info('Outline edit request: user=%s', callback.from_user.id)
    data = await state.get_data()
    outline = data.get('outline', [])
    if not outline:
        await callback.message.answer('План пустой 🙈 Нажмите «Перегенерировать».', reply_markup=outline_error_kb())
        return
    await state.set_state(PresentationStates.waiting_outline_edit)
    await callback.message.answer(
        _format_outline_edit(outline),
        parse_mode='HTML',
        reply_markup=outline_edit_kb(),
    )


@router.callback_query(F.data == 'outline:cancel')
async def handle_outline_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    logger.info('Outline cancel: user=%s', callback.from_user.id)
    await state.clear()
    await callback.message.answer('Главное меню 📌', reply_markup=main_menu_kb())


@router.message(PresentationStates.waiting_outline_edit)
async def handle_outline_edit(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer('Пришлите текст плана одним сообщением ✍️')
        return
    lines = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not lines:
        await message.answer('Не вижу плана 🙃 Отправь список строками.')
        return
    content_slides = len(lines)
    slides_total = content_slides + 1
    await state.update_data(outline=lines, slides=content_slides, slides_total=slides_total)
    logger.info('Outline edited: user=%s slides=%s', message.from_user.id, slides_total)
    await state.set_state(PresentationStates.waiting_outline_confirm)
    data = await state.get_data()
    title = data.get('title') or data.get('topic', '')
    text = _format_outline(lines, title)
    await message.answer(text, parse_mode='HTML')
    await message.answer(
        'Принять или изменить?\n'
        'Можно написать комментарий к плану, и я его обновлю.',
        reply_markup=outline_actions_kb(),
    )


@router.message(PresentationStates.waiting_outline_confirm)
async def handle_outline_confirm_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer('Пришлите комментарий текстом или нажмите кнопку 👇', reply_markup=outline_actions_kb())
        return
    comment = message.text.strip()
    if not comment:
        await message.answer('Напишите комментарий к плану или нажмите кнопку 👇', reply_markup=outline_actions_kb())
        return
    data = await state.get_data()
    topic = data.get('topic', '')
    outline = data.get('outline', [])
    content_slides = data.get('slides', len(outline) or 5)
    title = data.get('title') or topic
    if not outline:
        await message.answer('План пустой 🙈 Нажмите «Перегенерировать».', reply_markup=outline_error_kb())
        return
    logger.info('Outline comment: user=%s len=%s', message.from_user.id, len(comment))
    await message.answer('Применяю комментарий... ✍️')
    try:
        new_outline = await kie_client.generate_outline_with_comment(topic, content_slides, outline, comment)
    except KieError as exc:
        logger.warning('Outline comment failed: user=%s err=%s', message.from_user.id, exc)
        await notify_admins(
            message.bot,
            f'❌ Ошибка Kie.ai: {exc} (user {message.from_user.id} @{message.from_user.username or "-"})',
        )
        await message.answer(f'Не удалось обновить план 😢\n{exc}')
        return
    await state.update_data(outline=new_outline)
    logger.info(
        'Outline updated by comment: user=%s slides=%s topic="%s"',
        message.from_user.id,
        content_slides,
        _shorten_text(topic),
    )
    await notify_admins(
        message.bot,
        f'✍️ План обновлен по комментарию: пользователь {message.from_user.id} '
        f'(@{message.from_user.username or "-"}) тема "{_shorten_text(topic)}", слайдов {content_slides}',
    )
    text = _format_outline(new_outline, title)
    await message.answer(text, parse_mode='HTML')
    await message.answer(
        'Принять или изменить?\n'
        'Можно написать комментарий к плану, и я его обновлю.',
        reply_markup=outline_actions_kb(),
    )


@router.callback_query(F.data == 'outline:ok')
async def handle_outline_ok(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    logger.info('Outline approved: user=%s', callback.from_user.id)
    data = await state.get_data()
    if not data.get('outline'):
        await callback.message.answer('План пустой 🙈 Нажмите «Перегенерировать».', reply_markup=outline_error_kb())
        return
    await state.set_state(PresentationStates.waiting_design)
    await _send_design_previews(callback)
    await callback.message.answer('Выбери дизайн оформления 🎨', reply_markup=design_kb())


@router.callback_query(F.data.startswith('design:'))
async def handle_design(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    design = int(callback.data.split(':', 1)[1])
    await state.update_data(design=design)
    logger.info('Design selected: user=%s design=%s', callback.from_user.id, design)
    data = await state.get_data()
    if not data.get('topic') or not data.get('outline'):
        await callback.message.answer(
            'Сессия устарела 🙈\nНажмите «Создать презентацию» и начните заново.',
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return
    template_path = os.path.join(config.templates_dir, f'design_{design}.pptx')
    if not os.path.exists(template_path):
        await callback.message.answer(
            'Шаблон не найден 😢\n'
            'Пожалуйста, загрузите файл шаблона на сервер.',
            reply_markup=main_menu_button_kb(),
        )
        logger.error('Template missing: %s', template_path)
        await state.clear()
        return
    sub = await get_subscription_for_use(callback.from_user.id)
    if not sub:
        await state.set_state(PresentationStates.waiting_payment)
        await callback.message.answer(
            'Презентация почти готова! ✅\n'
            'Выбери подписку, чтобы завершить финальный шаг и получить готовую презентацию.',
            reply_markup=payment_options_kb(_build_payment_options(config)),
        )
        return
    await _run_generation(callback.bot, callback.message.chat.id, callback.from_user.id, state)


async def _send_design_previews(callback: CallbackQuery) -> None:
    previews: List[InputMediaPhoto] = []
    for i in range(1, 5):
        path = os.path.join(config.templates_dir, f'preview_{i}.jpg')
        if os.path.exists(path):
            previews.append(InputMediaPhoto(media=FSInputFile(path)))
    if previews:
        await callback.message.answer_media_group(previews)
    else:
        await callback.message.answer('Превью шаблонов пока не добавлены 🖼️')


async def _run_generation(bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    topic = data.get('topic')
    outline = data.get('outline')
    design = data.get('design')
    slides_count = data.get('slides_total') or data.get('slides')
    if not topic or not outline or not design:
        await bot.send_message(
            chat_id,
            'Сессия устарела 🙈\nНажмите «Создать презентацию» и начните заново.',
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return
    title = data.get('title') or topic
    logger.info('Generation start: user=%s slides=%s design=%s', user_id, slides_count, design)
    sub = await get_subscription_for_use(user_id)
    if not sub:
        await bot.send_message(
            chat_id,
            'Лимит подписки исчерпан 😔\nВыбери подписку 👇',
            reply_markup=payment_options_kb(_build_payment_options(config)),
        )
        await state.set_state(PresentationStates.waiting_payment)
        return

    status_msg = await bot.send_message(chat_id, 'Пишу тексты... ✍️')
    try:
        await asyncio.wait_for(
            _run_generation_steps(
                bot,
                chat_id,
                user_id,
                state,
                status_msg,
                topic,
                outline,
                title,
                design,
                slides_count,
            ),
            timeout=config.generation_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning('Generation timeout: user=%s', user_id)
        await log_generation(user_id, topic, slides_count, False)
        await _edit_status(status_msg, bot, chat_id, 'Произошла ошибка 😢')
        await bot.send_message(
            chat_id,
            'Генерация заняла слишком много времени ⏳\nПопробуйте еще раз позже.',
            reply_markup=main_menu_button_kb(),
        )
        try:
            chat = await bot.get_chat(user_id)
            username = chat.username or '-'
        except Exception:  # noqa: BLE001
            username = '-'
        await notify_admins(
            bot,
            f'❌ Ошибка генерации: таймаут (user {user_id} @{username})',
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Generation failed: user=%s', user_id)
        await log_generation(user_id, topic, slides_count, False)
        await _edit_status(status_msg, bot, chat_id, 'Произошла ошибка 😢')
        await bot.send_message(chat_id, f'Ошибка при генерации 😢\n{exc}', reply_markup=main_menu_button_kb())
        try:
            chat = await bot.get_chat(user_id)
            username = chat.username or '-'
        except Exception:  # noqa: BLE001
            username = '-'
        await notify_admins(
            bot,
            f'❌ Ошибка генерации: {exc} (user {user_id} @{username})',
        )
    finally:
        await state.clear()


async def _run_generation_steps(
    bot,
    chat_id: int,
    user_id: int,
    state: FSMContext,
    status_msg: Message,
    topic: str,
    outline: list,
    title: str,
    design: int,
    slides_count: int,
) -> None:
    slides = await kie_client.generate_slide_contents(topic, outline)

    await _edit_status(status_msg, bot, chat_id, 'Пишу тексты... ✅\nРисую иллюстрации... 🎨')
    temp_dir = config.temp_dir
    os.makedirs(temp_dir, exist_ok=True)

    semaphore = asyncio.Semaphore(config.image_concurrency)

    async def _build_payload(idx: int, slide: dict) -> tuple[int, dict]:
        async with semaphore:
            img_path = os.path.join(temp_dir, f'{user_id}_{uuid.uuid4().hex}_{idx}.png')
            image_path = await kie_client.generate_image(slide.get('image_prompt', ''), img_path)
            return idx, {
                'title': slide.get('title', f'Слайд {idx}'),
                'text': slide.get('text', ''),
                'image_path': image_path,
            }

    tasks = [_build_payload(idx, slide) for idx, slide in enumerate(slides, start=1)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda item: item[0])
    content_payloads = [payload for _, payload in results]
    slide_payloads = [{'title': title, 'text': '', 'image_path': None}] + content_payloads

    await _edit_status(status_msg, bot, chat_id, 'Пишу тексты... ✅\nРисую иллюстрации... ✅\nСобираю файл... 📂')
    template_path = os.path.join(config.templates_dir, f'design_{design}.pptx')
    output_pptx = os.path.join(temp_dir, f'presentation_{user_id}_{uuid.uuid4().hex}.pptx')

    await asyncio.to_thread(build_presentation, template_path, slide_payloads, output_pptx)
    output_pdf = None
    try:
        output_pdf = await asyncio.to_thread(convert_file, output_pptx, 'pdf', config.libreoffice_path)
    except Exception:  # noqa: BLE001
        logger.exception('PDF convert failed: user=%s', user_id)
    logger.info('Generation files: user=%s pptx=%s pdf=%s', user_id, output_pptx, output_pdf)
    pptx_name = _build_filename(title, 'pptx')
    pdf_name = _build_filename(title, 'pdf')
    await bot.send_document(
        chat_id,
        FSInputFile(output_pptx, filename=pptx_name),
        caption='📊 Презентация (PPTX) версия для редактирования',
    )
    if output_pdf:
        await bot.send_document(
            chat_id,
            FSInputFile(output_pdf, filename=pdf_name),
            caption='📄 Презентация (PDF) финальная версия для просмотра',
        )
    if config.send_docx and output_pdf:
        output_docx = await asyncio.to_thread(convert_file, output_pdf, 'docx', config.libreoffice_path)
        if output_docx:
            logger.info('Generation docx: user=%s docx=%s', user_id, output_docx)
            docx_name = _build_filename(title, 'docx')
            await bot.send_document(chat_id, FSInputFile(output_docx, filename=docx_name))

    if not await decrement_subscription(user_id):
        logger.warning('Failed to decrement subscription after success: user=%s', user_id)

    await log_generation(user_id, topic, slides_count, True)
    await _edit_status(status_msg, bot, chat_id, 'Готово! 🎉 Презентация создана.')
    await bot.send_message(chat_id, 'Презентация готова ✅', reply_markup=main_menu_button_kb())
    try:
        chat = await bot.get_chat(user_id)
        username = chat.username or '-'
    except Exception:  # noqa: BLE001
        username = '-'
    await notify_admins(
        bot,
        f'✅ Успешная генерация (Презентация). Пользователь {user_id} (@{username})',
    )


def _format_outline(items: List[str], title: str) -> str:
    import html

    safe_title = html.escape(title)
    lines = [f'<b>План презентации «{safe_title}» 📋</b>']
    for idx, item in enumerate(items, start=1):
        safe = html.escape(item)
        lines.append(f'<b>{idx}.</b> {safe}')
    return '\n'.join(lines)


def _format_outline_edit(items: List[str]) -> str:
    import html

    safe_lines = '\n'.join(f'{idx}. {item}' for idx, item in enumerate(items, start=1))
    safe_lines = html.escape(safe_lines)
    return (
        'Отправьте свой вариант плана одним сообщением.\n'
        'Каждый пункт — с новой строки.\n'
        'Текущий план:\n'
        f'<pre>{safe_lines}</pre>'
    )


def _shorten_text(value: str, max_len: int = 120) -> str:
    if not value:
        return ''
    cleaned = ' '.join(value.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + '…'


async def _edit_status(msg: Message, bot, chat_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=msg.message_id)
    except Exception:  # noqa: BLE001
        await bot.send_message(chat_id, text)


def _build_filename(title: str, ext: str) -> str:
    import re

    base = title.strip()
    base = re.sub(r'[^A-Za-zА-Яа-я0-9 _-]+', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    if not base:
        base = 'presentation'
    if len(base) > 60:
        base = base[:57].rstrip() + '...'
    return f'{base}.{ext}'


def _build_payment_options(cfg) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = [
        (f"🔥 {PLANS['week']['price_rub']} ₽ / неделя — {PLANS['week']['limit']} генераций", 'pay:week:yoo'),
        (f"⭐ {PLANS['month']['price_rub']} ₽ / месяц — {PLANS['month']['limit']} генераций", 'pay:month:yoo'),
    ]
    options += [
        (f"⭐ Купить {PLANS['one10']['limit']} генераций ({cfg.stars_one10_amount}⭐)", 'pay:one10:stars'),
        (f"⭐ Купить {PLANS['one40']['limit']} генераций ({cfg.stars_one40_amount}⭐)", 'pay:one40:stars'),
    ]
    return options
