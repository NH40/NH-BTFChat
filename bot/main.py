import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db import async_session_maker
from bot.handlers import routers
from bot.logging_setup import setup_logging
from bot.middlewares import DbSessionMiddleware
from bot.services.reconcile import run_reconciler
from bot.services.tournament.ticker import run_tournament_ticker


async def main() -> None:
    setup_logging()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware(async_session_maker))
    dp.include_routers(*routers)

    await bot.delete_webhook(drop_pending_updates=True)

    reconciler_task = asyncio.create_task(run_reconciler(bot))
    tournament_ticker_task = asyncio.create_task(run_tournament_ticker(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        reconciler_task.cancel()
        tournament_ticker_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
