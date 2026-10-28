"""Точка входа бота: middleware, роутеры, фоновые циклы (напоминания, повторы, проверка постов)."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from bot.config import settings
from bot.db import session_factory
from bot.handlers import chats, help as help_handlers, moderation, relay, start, tasks
from bot.middlewares.core import AntispamMiddleware, DbSessionMiddleware, TrackMiddleware
from bot.services import relay as relay_service
from bot.services import chats as chats_service
from bot.services import reminders, series
from bot.services.tasks import ensure_default_board

log = logging.getLogger(__name__)


async def _loop(name: str, interval: float, func, *args) -> None:
    while True:
        try:
            await func(*args)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("%s loop failed", name)
        await asyncio.sleep(interval)


async def _bootstrap(bot: Bot) -> None:
    async with session_factory() as session:
        await ensure_default_board(session)
        await chats_service.sync_bot_status(bot, session)
        await session.commit()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.message.outer_middleware(TrackMiddleware())
    dp.callback_query.outer_middleware(TrackMiddleware())
    dp.message.outer_middleware(AntispamMiddleware())
    dp.include_routers(help_handlers.router, start.router, chats.router, moderation.router, relay.router, tasks.router)

    await _bootstrap(bot)
    await bot.set_my_commands([
        BotCommand(command="start", description="Панель BTF"),
        BotCommand(command="tasks", description="Мои задачи"),
        BotCommand(command="help", description="Гайд по боту"),
    ], scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands([
        BotCommand(command="ban", description="Бан [срок] [причина]"),
        BotCommand(command="mute", description="Мут [срок] [причина]"),
        BotCommand(command="warn", description="Предупреждение"),
        BotCommand(command="kick", description="Исключить"),
        BotCommand(command="unban", description="Разбан"),
        BotCommand(command="unmute", description="Размут"),
        BotCommand(command="unwarn", description="Снять предупреждение"),
        BotCommand(command="warns", description="Предупреждения"),
        BotCommand(command="rules", description="Правила чата"),
        BotCommand(command="tasks", description="Мои задачи"),
        BotCommand(command="help", description="Команды бота"),
    ], scope=BotCommandScopeAllGroupChats())

    loops = [
        asyncio.create_task(_loop("reminders", 30, reminders.sweep, bot, session_factory)),
        asyncio.create_task(_loop("series", 60, series.sweep, bot, session_factory)),
        asyncio.create_task(_loop("relay_check", 60, relay_service.check_deleted, bot, session_factory)),
    ]
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in loops:
            task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
