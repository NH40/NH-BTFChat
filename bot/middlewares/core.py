"""Middleware: сессия БД на апдейт; запоминание пользователей и чатов; антиспам в группах."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db import Chat
from bot.db.models.chats import KIND_COMMUNITY
from bot.services import antispam, moderation, staff, users
from bot.services.moderation_settings import merged
from bot.utils.text import mention

log = logging.getLogger(__name__)
GROUPS = (ChatType.GROUP, ChatType.SUPERGROUP)


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class TrackMiddleware(BaseMiddleware):
    """Запоминает отправителя и (для групп) сам чат — чтобы находить людей по @username и
    видеть чаты, куда бота добавили до обновления."""

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        session: AsyncSession = data["session"]
        user = getattr(event, "from_user", None)
        if user is not None:
            await users.upsert(session, user)
        if isinstance(event, Message):
            if event.reply_to_message and event.reply_to_message.from_user:
                await users.upsert(session, event.reply_to_message.from_user)
            if event.chat.type in GROUPS:
                stmt = pg_insert(Chat).values(id=event.chat.id, title=event.chat.title, username=event.chat.username,
                                              type=event.chat.type, settings={})
                await session.execute(stmt.on_conflict_do_update(
                    index_elements=[Chat.id], set_={"title": stmt.excluded.title, "username": stmt.excluded.username}))
        await session.commit()
        return await handler(event, data)


async def _is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError:
        return False
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)


class AntispamMiddleware(BaseMiddleware):
    """Сообщения в модерируемых чатах: флуд, ссылки, слова, чужие пересылки → действие из настроек."""

    async def __call__(self, handler, event: Message, data: dict[str, Any]) -> Any:
        if event.chat.type not in GROUPS or event.from_user is None or event.from_user.is_bot:
            return await handler(event, data)
        session: AsyncSession = data["session"]
        chat = await session.get(Chat, event.chat.id)
        if chat is None or chat.kind != KIND_COMMUNITY:
            return await handler(event, data)
        cfg = merged(chat.settings)
        if not cfg["enabled"]:
            return await handler(event, data)
        if (event.text or "").startswith("/"):
            return await handler(event, data)  # команды не режем антиспамом
        bot: Bot = data["bot"]
        if cfg["ignore_staff"] and (
            await staff.role_of(session, event.from_user.id) or await _is_chat_admin(bot, chat.id, event.from_user.id)
        ):
            return await handler(event, data)
        violation = await antispam.check(event, cfg)
        if violation is None:
            return await handler(event, data)
        uid = event.from_user.id
        try:
            await event.delete()
        except TelegramAPIError:
            pass
        who = mention(uid, event.from_user.username, event.from_user.full_name)
        note = None
        try:
            if violation.action == "warn":
                res = await moderation.warn(bot, session, chat, uid, None, violation.reason)
                note = f"⚠️ {who}: предупреждение {res.count}/{res.limit} — {violation.reason}"
                if res.punished:
                    note += f". Лимит — {'бан' if res.punished == 'ban' else 'мут'}."
            elif violation.action == "mute":
                await moderation.mute(bot, session, chat.id, uid, None, timedelta(minutes=violation.mute_minutes), violation.reason)
                note = f"🔇 {who}: мут на {violation.mute_minutes} мин — {violation.reason}"
            elif violation.action == "ban":
                await moderation.ban(bot, session, chat.id, uid, None, None, violation.reason)
                note = f"⛔ {who}: бан — {violation.reason}"
            else:
                await moderation.log_delete(session, chat.id, uid, violation.reason)
        except moderation.ModerationError as exc:
            log.warning("antispam action failed in %s: %s", chat.id, exc)
        await session.commit()
        if note and cfg["log_actions"]:
            try:
                await bot.send_message(chat.id, note)
            except TelegramAPIError:
                pass
        return None  # сообщение обработано антиспамом — дальше не идёт


class CallbackSessionCommit(BaseMiddleware):
    """Подстраховка: коммит после callback-хендлера, если тот забыл (идемпотентно)."""

    async def __call__(self, handler, event: CallbackQuery, data: dict[str, Any]) -> Any:
        result = await handler(event, data)
        session: AsyncSession = data["session"]
        if session.in_transaction():
            await session.commit()
        return result
