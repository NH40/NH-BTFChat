"""Модерация: бан / разбан / мут / размут / кик / предупреждения — вызовы Telegram + журнал."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatPermissions
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Chat, ChatWarning, ModAction
from bot.db.models.moderation import (
    ACT_BAN, ACT_DELETE, ACT_KICK, ACT_MUTE, ACT_UNBAN, ACT_UNMUTE, ACT_UNWARN, ACT_WARN,
)
from bot.services.moderation_settings import merged
from bot.utils.time import now

log = logging.getLogger(__name__)

MUTED = ChatPermissions(can_send_messages=False)
UNMUTED = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True,
    can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True,
    can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True,
)


class ModerationError(Exception):
    """Telegram отказал (нет прав, цель — админ и т.п.)."""


@dataclass
class WarnResult:
    count: int
    limit: int
    punished: str | None  # действие при достижении лимита (mute/ban) или None


async def _log(session: AsyncSession, chat_id: int, target_id: int, actor_id: int | None, action: str,
               reason: str | None = None, until: datetime | None = None) -> None:
    session.add(ModAction(chat_id=chat_id, target_id=target_id, actor_id=actor_id, action=action, reason=reason, until=until))


def _until(duration: timedelta | None) -> datetime | None:
    # Telegram: срок < 30 с или > 366 дней = навсегда.
    return now() + duration if duration else None


async def ban(bot: Bot, session: AsyncSession, chat_id: int, user_id: int, actor_id: int | None,
              duration: timedelta | None = None, reason: str | None = None) -> datetime | None:
    until = _until(duration)
    try:
        await bot.ban_chat_member(chat_id, user_id, until_date=until)
    except TelegramAPIError as exc:
        raise ModerationError(str(exc)) from exc
    await _log(session, chat_id, user_id, actor_id, ACT_BAN, reason, until)
    return until


async def unban(bot: Bot, session: AsyncSession, chat_id: int, user_id: int, actor_id: int | None) -> None:
    try:
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
    except TelegramAPIError as exc:
        raise ModerationError(str(exc)) from exc
    await _log(session, chat_id, user_id, actor_id, ACT_UNBAN)


async def mute(bot: Bot, session: AsyncSession, chat_id: int, user_id: int, actor_id: int | None,
               duration: timedelta | None = None, reason: str | None = None) -> datetime | None:
    until = _until(duration)
    try:
        await bot.restrict_chat_member(chat_id, user_id, MUTED, until_date=until)
    except TelegramAPIError as exc:
        raise ModerationError(str(exc)) from exc
    await _log(session, chat_id, user_id, actor_id, ACT_MUTE, reason, until)
    return until


async def unmute(bot: Bot, session: AsyncSession, chat_id: int, user_id: int, actor_id: int | None) -> None:
    try:
        await bot.restrict_chat_member(chat_id, user_id, UNMUTED)
    except TelegramAPIError as exc:
        raise ModerationError(str(exc)) from exc
    await _log(session, chat_id, user_id, actor_id, ACT_UNMUTE)


async def kick(bot: Bot, session: AsyncSession, chat_id: int, user_id: int, actor_id: int | None,
               reason: str | None = None) -> None:
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
    except TelegramAPIError as exc:
        raise ModerationError(str(exc)) from exc
    await _log(session, chat_id, user_id, actor_id, ACT_KICK, reason)


async def active_warns(session: AsyncSession, chat_id: int, user_id: int, expire_days: int) -> int:
    since = now() - timedelta(days=expire_days) if expire_days else None
    q = select(func.count()).select_from(ChatWarning).where(
        ChatWarning.chat_id == chat_id, ChatWarning.user_id == user_id, ChatWarning.active.is_(True)
    )
    if since:
        q = q.where(ChatWarning.created_at >= since)
    return int(await session.scalar(q) or 0)


async def warn(bot: Bot, session: AsyncSession, chat: Chat, user_id: int, actor_id: int | None,
               reason: str | None = None) -> WarnResult:
    """Предупреждение; на лимите — наказание из настроек чата и обнуление предупреждений."""
    cfg = merged(chat.settings)["warns"]
    session.add(ChatWarning(chat_id=chat.id, user_id=user_id, reason=reason, issued_by=actor_id))
    await _log(session, chat.id, user_id, actor_id, ACT_WARN, reason)
    await session.flush()
    count = await active_warns(session, chat.id, user_id, cfg["expire_days"])
    punished = None
    if count >= cfg["limit"]:
        auto_reason = f"{count}/{cfg['limit']} предупреждений"
        if cfg["action"] == "ban":
            await ban(bot, session, chat.id, user_id, None, None, auto_reason)
        else:
            await mute(bot, session, chat.id, user_id, None, timedelta(minutes=cfg["mute_minutes"]), auto_reason)
        punished = cfg["action"]
        await session.execute(
            update(ChatWarning).where(ChatWarning.chat_id == chat.id, ChatWarning.user_id == user_id).values(active=False)
        )
    return WarnResult(count, cfg["limit"], punished)


async def unwarn(session: AsyncSession, chat_id: int, user_id: int, actor_id: int | None) -> int:
    """Снять последнее предупреждение. → сколько осталось."""
    last = await session.scalar(
        select(ChatWarning).where(ChatWarning.chat_id == chat_id, ChatWarning.user_id == user_id, ChatWarning.active.is_(True))
        .order_by(ChatWarning.created_at.desc()).limit(1)
    )
    if last is not None:
        last.active = False
        await _log(session, chat_id, user_id, actor_id, ACT_UNWARN)
    await session.flush()
    return int(await session.scalar(
        select(func.count()).select_from(ChatWarning).where(
            ChatWarning.chat_id == chat_id, ChatWarning.user_id == user_id, ChatWarning.active.is_(True))
    ) or 0)


async def log_delete(session: AsyncSession, chat_id: int, user_id: int, reason: str) -> None:
    await _log(session, chat_id, user_id, None, ACT_DELETE, reason)
