"""Задачи в Telegram: кнопки под напоминаниями (Взял / Готово / +1ч) и /tasks — мои задачи."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Task, TaskAssignee
from bot.db.models.users import ROLE_SENIOR
from bot.services import reminders, staff, tasks, workflow
from bot.utils.text import esc, mention
from bot.utils.time import fmt_dt

router = Router(name="tasks")


async def _allowed(session: AsyncSession, user_id: int, task: Task) -> bool:
    """Нажимать может исполнитель задачи или старший/владелец."""
    if staff.at_least(await staff.role_of(session, user_id), ROLE_SENIOR):
        return True
    return await session.get(TaskAssignee, (task.id, user_id)) is not None


@router.callback_query(F.data.startswith(reminders.CB_TAKE))
async def cb_take(callback: CallbackQuery, session: AsyncSession) -> None:
    task = await session.get(Task, int(callback.data.removeprefix(reminders.CB_TAKE)))
    if task is None or task.completed_at is not None:
        await callback.answer("Задача уже закрыта", show_alert=True)
        return
    if await staff.role_of(session, callback.from_user.id) is None:
        await callback.answer("Только для команды", show_alert=True)
        return
    await tasks.take(session, callback.from_user.id, task)
    await session.commit()
    u = callback.from_user
    await callback.answer("Взято в работу")
    await callback.message.reply(f"🙋 {mention(u.id, u.username, u.full_name)} взял задачу <b>#{task.id} {esc(task.title)}</b>")


@router.callback_query(F.data.startswith(reminders.CB_DONE))
async def cb_done(callback: CallbackQuery, session: AsyncSession) -> None:
    task = await session.get(Task, int(callback.data.removeprefix(reminders.CB_DONE)))
    if task is None:
        await callback.answer("Задача не найдена", show_alert=True)
        return
    if not await _allowed(session, callback.from_user.id, task):
        await callback.answer("Закрыть может исполнитель или старший", show_alert=True)
        return
    if not await workflow.complete(session, callback.from_user.id, task):
        await callback.answer("Уже выполнена", show_alert=True)
        return
    await session.commit()
    u = callback.from_user
    await callback.answer("Выполнено ✅")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ {mention(u.id, u.username, u.full_name)} выполнил <b>#{task.id} {esc(task.title)}</b>")


@router.callback_query(F.data.startswith(reminders.CB_SNOOZE))
async def cb_snooze(callback: CallbackQuery, session: AsyncSession) -> None:
    task_id, rem_id = (int(x) for x in callback.data.removeprefix(reminders.CB_SNOOZE).split(":"))
    task = await session.get(Task, task_id)
    if task is None or not await _allowed(session, callback.from_user.id, task):
        await callback.answer("Отложить может исполнитель или старший", show_alert=True)
        return
    await reminders.snooze(session, rem_id)
    await session.commit()
    await callback.answer(f"Напомню через {reminders.SNOOZE_MINUTES // 60} ч")


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, session: AsyncSession, bot: Bot) -> None:
    """Мои открытые задачи (в личке или в чате админов)."""
    if await staff.role_of(session, message.from_user.id) is None:
        return
    rows = list(await session.scalars(
        select(Task).join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .where(TaskAssignee.user_id == message.from_user.id, Task.completed_at.is_(None), Task.archived.is_(False))
        .order_by(Task.deadline.is_(None), Task.deadline, Task.priority.desc()).limit(30)
    ))
    if not rows:
        await message.reply("У тебя нет открытых задач 🎉")
        return
    lines = [f"<b>Твои задачи ({len(rows)}):</b>"]
    for t in rows:
        due = f" · ⏰ {fmt_dt(t.deadline)}" if t.deadline else ""
        lines.append(f"{reminders.PRIORITY_MARKS.get(t.priority, '🔹')} #{t.id} {esc(t.title)}{due}")
    await message.reply("\n".join(lines))
