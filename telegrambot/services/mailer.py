from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

from config import load_config
from database.models import (
    get_mailer_state,
    upsert_mailer_state,
    set_mailer_preview_sent,
    get_users_without_active_subscription,
    list_admins,
)
from keyboards.inline import mailer_cta_kb
from services.logger import get_logger


logger = get_logger()
UTC = timezone.utc
_LOCK = asyncio.Lock()


@dataclass
class MailerBlock:
    text: str


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_blocks(raw: str) -> list[MailerBlock]:
    blocks: list[MailerBlock] = []
    buf: list[str] = []
    for line in raw.splitlines():
        if line.strip() in ('---', '==='):
            text = '\n'.join(buf).strip()
            if text:
                blocks.append(MailerBlock(text=text))
            buf = []
            continue
        buf.append(line)
    text = '\n'.join(buf).strip()
    if text:
        blocks.append(MailerBlock(text=text))
    return blocks


def _short(text: str, limit: int = 80) -> str:
    value = ' '.join(text.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + '…'


def _template_path(config) -> str:
    return f"{config.templates_dir}/design_{config.mailer_template_index}.txt"


async def _get_admin_ids(config) -> list[int]:
    extra = await list_admins()
    return sorted(set(config.admin_ids + extra))


async def mailer_loop(bot, config) -> None:
    if not config.mailer_enabled:
        logger.info('Mailer disabled')
        return
    logger.info('Mailer loop started')
    while True:
        try:
            await _mailer_tick(bot, config)
        except Exception:  # noqa: BLE001
            logger.exception('Mailer tick failed')
        await asyncio.sleep(config.mailer_tick_seconds)


async def _mailer_tick(bot, config) -> None:
    if _LOCK.locked():
        return
    blocks = _load_blocks(config)
    if not blocks:
        return
    state = await get_mailer_state()
    now = _now()
    if not state:
        next_run_at = now + timedelta(minutes=config.mailer_preview_minutes)
        preview_at = now
        await upsert_mailer_state(0, next_run_at.isoformat(), preview_at.isoformat(), 0)
        state = await get_mailer_state()
        if not state:
            return
    preview_sent = state.get('preview_sent', 0)
    try:
        next_run_at = datetime.fromisoformat(state['next_run_at'])
        preview_at = datetime.fromisoformat(state['preview_at'])
    except Exception:  # noqa: BLE001
        next_run_at = now + timedelta(minutes=config.mailer_preview_minutes)
        preview_at = now
        await upsert_mailer_state(state.get('current_index', 0), next_run_at.isoformat(), preview_at.isoformat(), 0)
        preview_sent = 0

    if now >= preview_at and not preview_sent:
        await _send_preview(bot, config, blocks, state.get('current_index', 0))
        await set_mailer_preview_sent(1)
        return

    if now >= next_run_at and preview_sent:
        async with _LOCK:
            await _run_broadcast(bot, config, blocks, state.get('current_index', 0))


def _load_blocks(config) -> list[MailerBlock]:
    path = _template_path(config)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.read()
    except OSError:
        logger.warning('Mailer template not found: %s', path)
        return []
    blocks = _parse_blocks(raw)
    if not blocks:
        logger.warning('Mailer template has no blocks: %s', path)
    return blocks


async def _send_preview(bot, config, blocks: list[MailerBlock], index: int) -> None:
    admins = await _get_admin_ids(config)
    if not admins:
        return
    block = blocks[index % len(blocks)]
    text_short = _short(block.text)
    warn_text = (
        '⚠️ Внимание! Через 30 минут начнется автоматическая рассылка.\n'
        f'Текст: {text_short}'
    )
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, warn_text)
        except Exception:  # noqa: BLE001
            continue
        try:
            await bot.send_message(admin_id, block.text, reply_markup=mailer_cta_kb())
        except Exception:  # noqa: BLE001
            continue


async def _run_broadcast(bot, config, blocks: list[MailerBlock], index: int) -> None:
    admins = await _get_admin_ids(config)
    block = blocks[index % len(blocks)]
    audience = await get_users_without_active_subscription()
    total = len(audience)

    text_short = _short(block.text)
    start_text = (
        '🚀 Рассылка началась!\n'
        f'Текст: {text_short}\n'
        f'Целевая аудитория: {total} чел.'
    )
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, start_text)
        except Exception:  # noqa: BLE001
            continue

    progress_ids = await _send_progress(bot, admins, 0, total, 0)
    sent = 0
    blocked = 0
    errors = 0
    last_progress = _now()
    delay = 1.0 / max(config.mailer_rate_per_sec, 1)

    for user in audience:
        user_id = user['id']
        try:
            await bot.send_message(user_id, block.text, reply_markup=mailer_cta_kb())
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(max(exc.retry_after, 1))
            try:
                await bot.send_message(user_id, block.text, reply_markup=mailer_cta_kb())
                sent += 1
            except TelegramForbiddenError:
                blocked += 1
            except TelegramBadRequest:
                errors += 1
            except Exception:  # noqa: BLE001
                errors += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramBadRequest:
            errors += 1
        except Exception:  # noqa: BLE001
            errors += 1

        if delay > 0:
            await asyncio.sleep(delay)

        now = _now()
        if (now - last_progress).total_seconds() >= 60:
            await _edit_progress(bot, progress_ids, sent, total, blocked)
            last_progress = now

    await _edit_progress(bot, progress_ids, sent, total, blocked)
    await _finish_admins(bot, admins, sent, blocked, errors, index, len(blocks), config)
    await _schedule_next(index, len(blocks), config)


async def _send_progress(bot, admins: Iterable[int], sent: int, total: int, blocked: int) -> dict[int, int]:
    ids: dict[int, int] = {}
    text = _progress_text(sent, total, blocked)
    for admin_id in admins:
        try:
            msg = await bot.send_message(admin_id, text)
            ids[admin_id] = msg.message_id
        except Exception:  # noqa: BLE001
            continue
    return ids


async def _edit_progress(bot, ids: dict[int, int], sent: int, total: int, blocked: int) -> None:
    text = _progress_text(sent, total, blocked)
    for admin_id, msg_id in ids.items():
        try:
            await bot.edit_message_text(text, chat_id=admin_id, message_id=msg_id)
        except Exception:  # noqa: BLE001
            continue


def _progress_text(sent: int, total: int, blocked: int) -> str:
    percent = int((sent / total) * 100) if total else 0
    return (
        '⏳ Идет рассылка...\n'
        f'Отправлено: {sent} из {total} ({percent}%)\n'
        f'Ошибок/Блокировок: {blocked}'
    )


async def _finish_admins(
    bot,
    admins: Iterable[int],
    sent: int,
    blocked: int,
    errors: int,
    index: int,
    total_blocks: int,
    config,
) -> None:
    next_msg = f'Следующая рассылка через {config.mailer_pause_hours} часов.'
    lines = [
        '✅ Рассылка завершена.',
        f'Успешно доставлено: {sent}',
        f'Не доставлено (бот заблокирован): {blocked}',
        next_msg,
    ]
    if errors:
        lines.append(f'Ошибок: {errors}')
    text = '\n'.join(lines)
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            continue


async def _schedule_next(index: int, total_blocks: int, config) -> None:
    now = _now()
    if total_blocks == 0:
        return
    next_index = (index + 1) % total_blocks
    next_run_at = now + timedelta(hours=config.mailer_pause_hours)
    preview_at = next_run_at - timedelta(minutes=config.mailer_preview_minutes)
    await upsert_mailer_state(next_index, next_run_at.isoformat(), preview_at.isoformat(), 0)
