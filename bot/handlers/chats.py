"""Учёт чатов и каналов, куда добавили бота, и приветствие новичков."""
from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Chat
from bot.db.models.chats import KIND_CHANNEL, KIND_COMMUNITY
from bot.services.chats import status_of
from bot.services.moderation_settings import merged
from bot.utils.text import esc

router = Router(name="chats")


@router.my_chat_member()
async def on_my_status(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """Бота добавили/повысили/убрали: обновляем реестр чатов (их назначение выбирают в Mini App)."""
    chat = event.chat
    bot_status = status_of(event.new_chat_member.status)
    stmt = pg_insert(Chat).values(
        id=chat.id, title=chat.title, username=chat.username, type=chat.type, bot_status=bot_status, settings={},
        kind=KIND_CHANNEL if chat.type == "channel" else "none",
    )
    await session.execute(stmt.on_conflict_do_update(
        index_elements=[Chat.id],
        set_={"title": stmt.excluded.title, "username": stmt.excluded.username, "bot_status": stmt.excluded.bot_status},
    ))
    await session.commit()


@router.message(F.new_chat_members)
async def on_join(message: Message, session: AsyncSession, bot: Bot) -> None:
    chat = await session.get(Chat, message.chat.id)
    if chat is None or chat.kind != KIND_COMMUNITY:
        return
    cfg = merged(chat.settings)["welcome"]
    if not cfg["enabled"]:
        return
    for member in message.new_chat_members:
        if member.is_bot:
            continue
        text = cfg["text"].replace("{name}", esc(member.full_name)).replace("{username}", esc(member.username or member.full_name))
        try:
            sent = await message.answer(text)
        except TelegramAPIError:
            continue
        if cfg["delete_after_seconds"]:
            async def drop(msg_id: int = sent.message_id) -> None:
                await asyncio.sleep(int(cfg["delete_after_seconds"]))
                try:
                    await bot.delete_message(message.chat.id, msg_id)
                except TelegramAPIError:
                    pass

            asyncio.create_task(drop())
