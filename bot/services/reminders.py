"""Напоминания по задачам: расчёт следующего срока и рассылка в чат админов с @упоминаниями.

Виды (`db/models/tasks.REM_*`):
- before  — за `offset_minutes` до дедлайна (один раз);
- at      — в момент `at` (один раз);
- repeat  — с `at` (или сразу) каждые `interval_minutes`, пока задача не выполнена;
- overdue — после дедлайна: сразу и далее каждые `interval_minutes` (0 — только один раз).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import settings
from bot.db import Board, ChecklistItem, Task, TaskReminder
from bot.db.models.tasks import REM_AT, REM_BEFORE, REM_OVERDUE, REM_REPEAT, REMINDER_KINDS
from bot.services import app_settings, users
from bot.services.tasks import assignee_ids, history
from bot.utils.text import esc, mention
from bot.utils.time import fmt_dt, human_duration, now

log = logging.getLogger(__name__)

CB_TAKE = "t:take:"
CB_DONE = "t:done:"
CB_SNOOZE = "t:snooze:"  # + task_id:reminder_id
SNOOZE_MINUTES = 60
PRIORITY_MARKS = {0: "▫️", 1: "🔹", 2: "🔸", 3: "🔴"}


def compute_next(rem: TaskReminder, task: Task, t: datetime | None = None) -> datetime | None:
    """Когда сработать в следующий раз (None — больше не срабатывать)."""
    t = t or now()
    if task.completed_at is not None or task.archived:
        return None
    if rem.kind == REM_BEFORE:
        if task.deadline is None or rem.sent_count:
            return None
        at = task.deadline - timedelta(minutes=rem.offset_minutes or 0)
        return at if at > t else (t if task.deadline > t else None)
    if rem.kind == REM_AT:
        if rem.sent_count or rem.at is None:
            return None
        return rem.at if rem.at > t - timedelta(minutes=5) else None
    if rem.kind == REM_REPEAT:
        step = timedelta(minutes=max(5, rem.interval_minutes or 60))
        if rem.last_sent_at is None:
            return max(rem.at or t, t)
        return rem.last_sent_at + step
    if rem.kind == REM_OVERDUE:
        if task.deadline is None:
            return None
        if not rem.sent_count:
            return max(task.deadline, t) if task.deadline > t else t
        if rem.interval_minutes:
            return rem.last_sent_at + timedelta(minutes=max(5, rem.interval_minutes))
        return None
    return None


async def set_reminders(session: AsyncSession, task: Task, items: list[dict]) -> None:
    """Заменить напоминания задачи (НЕ коммитит). items: [{kind, offset_minutes, at, interval_minutes, text}]."""
    for rem in await session.scalars(select(TaskReminder).where(TaskReminder.task_id == task.id)):
        await session.delete(rem)
    await session.flush()
    for item in items:
        if item.get("kind") not in REMINDER_KINDS:
            continue
        rem = TaskReminder(
            task_id=task.id, kind=item["kind"], offset_minutes=item.get("offset_minutes"),
            at=item.get("at"), interval_minutes=item.get("interval_minutes"), text=(item.get("text") or None),
        )
        rem.next_at = compute_next(rem, task)
        rem.active = rem.next_at is not None
        session.add(rem)
    await session.flush()


async def apply_defaults(session: AsyncSession, task: Task) -> None:
    """Напоминания по умолчанию (из настроек) — новой задаче с дедлайном."""
    if task.deadline is None:
        return
    defaults = (await app_settings.get(session, app_settings.KEY_REMINDER_DEFAULTS)).get("items", [])
    await set_reminders(session, task, defaults)


async def recompute(session: AsyncSession, task: Task, reset_deadline_based: bool = False) -> None:
    """Пересчитать сроки напоминаний (срок задачи поменялся / задачу переоткрыли)."""
    for rem in await session.scalars(select(TaskReminder).where(TaskReminder.task_id == task.id)):
        if reset_deadline_based and rem.kind in (REM_BEFORE, REM_OVERDUE):
            rem.sent_count = 0
            rem.last_sent_at = None
        rem.next_at = compute_next(rem, task)
        rem.active = rem.next_at is not None


def task_keyboard(task_id: int, reminder_id: int | None = None) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text="🙋 Взял", callback_data=f"{CB_TAKE}{task_id}"),
        InlineKeyboardButton(text="✅ Готово", callback_data=f"{CB_DONE}{task_id}"),
    ]
    if reminder_id is not None:
        row.append(InlineKeyboardButton(text=f"⏰ +{SNOOZE_MINUTES // 60} ч", callback_data=f"{CB_SNOOZE}{task_id}:{reminder_id}"))
    rows = [row]
    if settings.mini_app_url:
        rows.append([InlineKeyboardButton(text="📋 Открыть в BTF", url=f"{settings.mini_app_url.rstrip('/')}/?task={task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def render(session: AsyncSession, task: Task, header: str, extra: str | None = None) -> str:
    """Карточка задачи для чата админов: кому, что, срок, подзадачи."""
    board = await session.get(Board, task.board_id)
    ids = await assignee_ids(session, task.id)
    people = await users.get_many(session, ids)
    who = ", ".join(mention(u.id, u.username, u.display_name) for u in people.values()) or "<i>исполнитель не назначен</i>"
    lines = [f"{header} · {esc(board.name if board else '')}",
             f"{PRIORITY_MARKS.get(task.priority, '🔹')} <b>#{task.id} {esc(task.title)}</b>",
             f"👥 {who}"]
    if task.deadline:
        t = now()
        kind = "жёсткий" if task.deadline_hard else "ориентир"
        if task.deadline < t and task.completed_at is None:
            lines.append(f"⏰ Срок: {fmt_dt(task.deadline)} — <b>просрочено на {human_duration(t - task.deadline)}</b>")
        else:
            lines.append(f"⏰ Срок: {fmt_dt(task.deadline)} ({kind})")
    total, done = (await session.execute(
        select(func.count(), func.count().filter(ChecklistItem.done)).where(ChecklistItem.task_id == task.id)
    )).one()
    if total:
        lines.append(f"☑️ Подзадачи: {done}/{total}")
    if extra:
        lines.append(f"💬 {esc(extra)}")
    return "\n".join(lines)


async def _admin_chat(session: AsyncSession) -> int | None:
    return (await app_settings.get(session, app_settings.KEY_ADMIN_CHAT)).get("chat_id")


async def announce(bot: Bot, session: AsyncSession, task: Task, header: str, extra: str | None = None,
                   reminder_id: int | None = None) -> bool:
    chat_id = await _admin_chat(session)
    if not chat_id:
        return False
    text = await render(session, task, header, extra)
    try:
        await bot.send_message(int(chat_id), text, reply_markup=task_keyboard(task.id, reminder_id), disable_web_page_preview=True)
    except TelegramAPIError:
        log.exception("Не удалось отправить напоминание в чат админов")
        return False
    return True


async def sweep(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Разослать наступившие напоминания. Несколько сработавших у одной задачи — одно сообщение."""
    sent = 0
    async with session_factory() as session:
        t = now()
        due = list(await session.scalars(
            select(TaskReminder).where(TaskReminder.active.is_(True), TaskReminder.next_at <= t)
            .order_by(TaskReminder.next_at).limit(50)
        ))
        by_task: dict[int, list[TaskReminder]] = {}
        for rem in due:
            by_task.setdefault(rem.task_id, []).append(rem)
        for task_id, rems in by_task.items():
            task = await session.get(Task, task_id)
            if task is None or task.completed_at is not None or task.archived:
                await session.execute(update(TaskReminder).where(TaskReminder.task_id == task_id).values(active=False))
                continue
            overdue = task.deadline is not None and task.deadline < t
            header = "🚨 Просрочено" if overdue else "🔔 Напоминание"
            extra = next((r.text for r in rems if r.text), None)
            if await announce(bot, session, task, header, extra, rems[0].id):
                sent += 1
            for rem in rems:
                rem.last_sent_at = t
                rem.sent_count += 1
                rem.next_at = compute_next(rem, task, t + timedelta(seconds=1))
                rem.active = rem.next_at is not None
            history(session, task.id, None, "reminded")
        await session.commit()
    return sent


async def snooze(session: AsyncSession, reminder_id: int, minutes: int = SNOOZE_MINUTES) -> None:
    rem = await session.get(TaskReminder, reminder_id)
    if rem is not None:
        rem.next_at = now() + timedelta(minutes=minutes)
        rem.active = True
