"""Посты и правки в каналах → пересылка в чаты связок."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.types import Message

from bot.db import session_factory
from bot.services import relay

router = Router(name="relay")


@router.channel_post()
async def on_post(message: Message, bot: Bot) -> None:
    await relay.on_channel_post(bot, session_factory, message.chat.id, message.message_id, message.media_group_id)


@router.edited_channel_post()
async def on_edit(message: Message, bot: Bot) -> None:
    await relay.on_edit(bot, session_factory, message.chat.id, message.message_id)
