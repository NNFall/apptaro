import asyncio
import os
import re
import uuid

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.types.input_file import FSInputFile

from config import load_config
from database.models import get_active_subscription
from keyboards.inline import main_menu_button_kb
from services.converter import convert_file
from services.logger import get_logger
from services.admin_notify import notify_admins

router = Router()
config = load_config()
logger = get_logger()


class ConverterStates(StatesGroup):
    pdf_to_docx = State()
    docx_to_pdf = State()
    pptx_to_pdf = State()


@router.callback_query(F.data == 'menu:pdf2docx')
async def ask_pdf_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ConverterStates.pdf_to_docx)
    logger.info('Menu click: pdf2docx user=%s', callback.from_user.id)
    await callback.message.answer('Отправьте PDF файл 📄')
    await callback.answer()


@router.callback_query(F.data == 'menu:docx2pdf')
async def ask_docx_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ConverterStates.docx_to_pdf)
    logger.info('Menu click: docx2pdf user=%s', callback.from_user.id)
    await callback.message.answer('Отправьте DOCX файл 📄')
    await callback.answer()


@router.callback_query(F.data == 'menu:pptx2pdf')
async def ask_pptx_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ConverterStates.pptx_to_pdf)
    logger.info('Menu click: pptx2pdf user=%s', callback.from_user.id)
    await callback.message.answer('Отправьте PPTX файл 📊')
    await callback.answer()


@router.message(F.text == 'PDF → DOCX')
async def ask_pdf(message: Message, state: FSMContext) -> None:
    await state.set_state(ConverterStates.pdf_to_docx)
    await message.answer('Отправьте PDF файл 📄')


@router.message(Command('pdf2docx'))
async def ask_pdf_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(ConverterStates.pdf_to_docx)
    await message.answer('Отправьте PDF файл 📄')


@router.message(F.text == 'DOCX → PDF')
async def ask_docx(message: Message, state: FSMContext) -> None:
    await state.set_state(ConverterStates.docx_to_pdf)
    await message.answer('Отправьте DOCX файл 📄')


@router.message(Command('docx2pdf'))
async def ask_docx_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(ConverterStates.docx_to_pdf)
    await message.answer('Отправьте DOCX файл 📄')


@router.message(F.text == 'PPTX → PDF')
async def ask_pptx(message: Message, state: FSMContext) -> None:
    await state.set_state(ConverterStates.pptx_to_pdf)
    await message.answer('Отправьте PPTX файл 📊')


@router.message(Command('pptx2pdf'))
async def ask_pptx_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(ConverterStates.pptx_to_pdf)
    await message.answer('Отправьте PPTX файл 📊')


@router.message(ConverterStates.pdf_to_docx, F.document)
async def handle_pdf_to_docx(message: Message, state: FSMContext) -> None:
    await _handle_conversion(message, state, 'docx')


@router.message(ConverterStates.docx_to_pdf, F.document)
async def handle_docx_to_pdf(message: Message, state: FSMContext) -> None:
    await _handle_conversion(message, state, 'pdf')


@router.message(ConverterStates.pptx_to_pdf, F.document)
async def handle_pptx_to_pdf(message: Message, state: FSMContext) -> None:
    await _handle_conversion(message, state, 'pdf')


async def _handle_conversion(message: Message, state: FSMContext, output_ext: str) -> None:
    temp_dir = config.temp_dir
    os.makedirs(temp_dir, exist_ok=True)
    job_dir = os.path.join(temp_dir, f'conv_{message.from_user.id}_{uuid.uuid4().hex}')
    os.makedirs(job_dir, exist_ok=True)
    if message.document.file_size and message.document.file_size > config.max_upload_mb * 1024 * 1024:
        await message.answer(
            f'Файл слишком большой 😥\nМаксимум {config.max_upload_mb} МБ.',
        )
        await state.clear()
        return
    original_name = message.document.file_name or 'file'
    filename = f'{message.from_user.id}_{uuid.uuid4().hex}_{original_name}'
    input_path = os.path.join(job_dir, filename)

    await message.bot.download(message.document, destination=input_path)
    logger.info('Convert request: user=%s input=%s output=%s', message.from_user.id, input_path, output_ext)
    await message.answer('Конвертирую файл... ⏳')

    try:
        output_path = await asyncio.to_thread(
            convert_file,
            input_path,
            output_ext,
            config.libreoffice_path,
            job_dir,
        )
        if not output_path:
            await message.answer('Не удалось конвертировать файл 😢')
            return
        output_path = await _rename_output(
            output_path,
            job_dir,
            original_name,
            output_ext,
            message,
        )
        logger.info('Convert done: user=%s output=%s', message.from_user.id, output_path)
        await message.answer_document(FSInputFile(output_path))
        await message.answer('Готово ✅\nКонвертация файла выполнена', reply_markup=main_menu_button_kb())
        input_ext = os.path.splitext(original_name)[1].lstrip('.').upper() or 'FILE'
        output_label = output_ext.upper()
        await notify_admins(
            message.bot,
            f'✅ Конвертация выполнена ({input_ext}→{output_label}). Пользователь {message.from_user.id} (@{message.from_user.username or "-"})',
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Convert failed: user=%s', message.from_user.id)
        await message.answer(f'Ошибка конвертации 😢\n{exc}')
        await notify_admins(
            message.bot,
            f'❌ Ошибка конвертации: {exc} (user {message.from_user.id} @{message.from_user.username or "-"})',
        )
    finally:
        await state.clear()


def _sanitize_filename(value: str, max_len: int = 80) -> str:
    value = value.strip().replace('\n', ' ')
    value = re.sub(r'[\\/:*?"<>|]+', '_', value)
    value = re.sub(r'\s+', ' ', value)
    if len(value) > max_len:
        value = value[:max_len].rstrip()
    return value or 'file'


async def _rename_output(
    output_path: str,
    job_dir: str,
    original_name: str,
    output_ext: str,
    message: Message,
) -> str:
    base = os.path.splitext(original_name)[0]
    base = _sanitize_filename(base)
    sub = await get_active_subscription(message.from_user.id)
    plan = sub['plan'] if sub else 'free'
    try:
        me = await message.bot.get_me()
        bot_name = me.username or 'bot'
    except Exception:  # noqa: BLE001
        bot_name = 'bot'
    suffix = _sanitize_filename(f'{plan}_{bot_name}', max_len=40)
    new_base = _sanitize_filename(f'{base}_{suffix}')
    new_path = os.path.join(job_dir, f'{new_base}.{output_ext}')
    if os.path.abspath(output_path) != os.path.abspath(new_path):
        if os.path.exists(new_path):
            new_path = os.path.join(job_dir, f'{new_base}_{uuid.uuid4().hex[:6]}.{output_ext}')
        os.replace(output_path, new_path)
    return new_path
