"""Реестр чатов: сверка статуса бота при старте (после переноса данных и простоя
my_chat_member могли не прийти)."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Chat

log = logging.getLogger(__name__)


def status_of(member_status: str) -> str:
    if member_status in ("left", "kicked"):
        return "left"
    return "administrator" if member_status in ("administrator", "creator") else "member"


async def sync_bot_status(bot: Bot, session: AsyncSession) -> None:
    """Обновить bot_status и название всех известных чатов (НЕ коммитит)."""
    me = await bot.me()
    for chat in await session.scalars(select(Chat).where(Chat.bot_status != "left")):
        try:
            member = await bot.get_chat_member(chat.id, me.id)
            info = await bot.get_chat(chat.id)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            log.warning("chat %s недоступен: %s", chat.id, exc)
            chat.bot_status = "left"
            continue
        except Exception:
            log.exception("chat %s: сверка не удалась", chat.id)
            continue
        chat.bot_status = status_of(member.status)
        chat.title = info.title or chat.title
        chat.username = info.username
