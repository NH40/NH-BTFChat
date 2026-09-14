from __future__ import annotations

import asyncio
import datetime as dt
import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import TASK_REMINDER_NAG_INTERVAL, TASK_REMINDER_POLL_SECONDS
from bot.db import Task, async_session_maker
from bot.services import tasks as task_service
from bot.texts import tasks as texts

logger = logging.getLogger(__name__)

_PRE_REMINDER_OFFSETS = {
    "before_1h": dt.timedelta(hours=1),
    "before_1d": dt.timedelta(days=1),
}


async def run_task_reminders(bot: Bot) -> None:
    while True:
        try:
            await asyncio.sleep(TASK_REMINDER_POLL_SECONDS)
            await _check_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Task reminder pass failed")


async def _check_once(bot: Bot) -> None:
    async with async_session_maker() as session:
        for task in await task_service.list_tasks_due_for_reminder(session):
            await _process_task(session, bot, task)


async def _process_task(session: AsyncSession, bot: Bot, task: Task) -> None:
    now = dt.datetime.utcnow()
    admin_chat = task.admin_chat
    if admin_chat is None or task.deadline is None:
        return

    offset = _PRE_REMINDER_OFFSETS.get(task.reminder_policy)
    if offset and not task.pre_reminder_sent and now >= task.deadline - offset and now < task.deadline:
        await _send(bot, admin_chat.tg_chat_id, texts.pre_reminder_text(task))
        await task_service.mark_pre_reminder_sent(session, task.id)
        return

    if now >= task.deadline and not task.deadline_notified:
        await _send(bot, admin_chat.tg_chat_id, texts.deadline_reached_text(task))
        await task_service.mark_deadline_notified(session, task.id, now)
        return

    if (
        task.deadline_notified
        and task.reminder_policy == "daily_until_done"
        and (task.last_reminded_at is None or now - task.last_reminded_at >= TASK_REMINDER_NAG_INTERVAL)
    ):
        await _send(bot, admin_chat.tg_chat_id, texts.overdue_nag_text(task))
        await task_service.touch_last_reminded(session, task.id, now)


async def _send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("Failed to send task reminder to %s", chat_id)
