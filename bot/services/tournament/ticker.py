from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bot.constant import TOURNAMENT_TICK_SECONDS
from bot.db import async_session_maker
from bot.services.tournament import matches as match_service
from bot.texts import tournament as texts

logger = logging.getLogger(__name__)


async def run_tournament_ticker(bot: Bot) -> None:
    while True:
        try:
            await asyncio.sleep(TOURNAMENT_TICK_SECONDS)
            await _tick_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Tournament ticker pass failed")


async def _tick_once(bot: Bot) -> None:
    async with async_session_maker() as session:
        due_matches = await match_service.matches_due_for_reminder(session)
        for match in due_matches:
            try:
                await bot.send_message(
                    match.chat_id, texts.TIME_UP_REMINDER.format(phase=match.status, match_id=match.id)
                )
            except Exception:
                logger.exception("Failed to send phase reminder for match %s", match.id)
            await match_service.mark_reminder_sent(session, match)
