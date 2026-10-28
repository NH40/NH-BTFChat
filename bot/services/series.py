"""Цикличные задачи (серии): правило повтора, следующая дата, создание очередной копии.

Правило (`TaskSeries.rule`):
- {"type": "interval", "n": 3, "unit": "hours"|"days", "start": ISO}  — каждые N часов/дней от start;
- {"type": "weekly", "weekdays": [0..6], "time": "HH:MM"}            — по дням недели (0 = пн);
- {"type": "monthly", "day": 1..31, "time": "HH:MM"}                 — N-го числа (в коротком месяце — последнего).
Время — в часовом поясе команды (settings.timezone).
Режим: schedule — копия по расписанию всегда; after_done — следующая копия только после
выполнения предыдущей, в ближайший слот правила после выполнения.
"""
from __future__ import annotations

import calendar
import logging
from datetime import datetime, time, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import settings
from bot.db import ChecklistItem, Task, TaskReminder, TaskSeries
from bot.db.models.tasks import REM_AT, RULE_INTERVAL, RULE_MONTHLY, RULE_WEEKLY, SERIES_AFTER_DONE, SERIES_SCHEDULE
from bot.services import reminders, tasks
from bot.utils.time import now

log = logging.getLogger(__name__)


class SeriesError(Exception):
    pass


def _parse_time(raw: str | None) -> time:
    try:
        h, m = (raw or "10:00").split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError) as exc:
        raise SeriesError("Время в формате ЧЧ:ММ") from exc


def validate(rule: dict) -> dict:
    kind = rule.get("type")
    if kind == RULE_INTERVAL:
        n = int(rule.get("n") or 0)
        if n <= 0 or rule.get("unit") not in ("hours", "days"):
            raise SeriesError("Интервал: N > 0, единица — часы или дни")
        start = rule.get("start") or now().isoformat()
        datetime.fromisoformat(start)
        return {"type": kind, "n": n, "unit": rule["unit"], "start": start}
    if kind == RULE_WEEKLY:
        days = sorted({int(d) for d in rule.get("weekdays") or [] if 0 <= int(d) <= 6})
        if not days:
            raise SeriesError("Выберите хотя бы один день недели")
        _parse_time(rule.get("time"))
        return {"type": kind, "weekdays": days, "time": rule.get("time") or "10:00"}
    if kind == RULE_MONTHLY:
        day = int(rule.get("day") or 0)
        if not 1 <= day <= 31:
            raise SeriesError("Число месяца — от 1 до 31")
        _parse_time(rule.get("time"))
        return {"type": kind, "day": day, "time": rule.get("time") or "10:00"}
    raise SeriesError("Неизвестный тип повтора")


def next_occurrence(rule: dict, after: datetime) -> datetime:
    """Первая дата правила строго позже `after` (UTC на входе и выходе)."""
    tz = settings.tz
    kind = rule["type"]
    if kind == RULE_INTERVAL:
        step = timedelta(hours=rule["n"]) if rule["unit"] == "hours" else timedelta(days=rule["n"])
        start = datetime.fromisoformat(rule["start"])
        if start.tzinfo is None:
            start = start.replace(tzinfo=tz)
        if start > after:
            return start
        k = int((after - start) / step) + 1
        return start + k * step
    at = _parse_time(rule["time"])
    local_after = after.astimezone(tz)
    if kind == RULE_WEEKLY:
        for add in range(0, 8):
            day = local_after.date() + timedelta(days=add)
            if day.weekday() in rule["weekdays"]:
                cand = datetime.combine(day, at, tzinfo=tz)
                if cand > local_after:
                    return cand.astimezone(after.tzinfo)
    if kind == RULE_MONTHLY:
        y, m = local_after.year, local_after.month
        for _ in range(14):
            day = min(rule["day"], calendar.monthrange(y, m)[1])
            cand = datetime.combine(datetime(y, m, day).date(), at, tzinfo=tz)
            if cand > local_after:
                return cand.astimezone(after.tzinfo)
            m += 1
            if m > 12:
                y, m = y + 1, 1
    raise SeriesError("Не удалось вычислить следующую дату")


def describe(rule: dict) -> str:
    names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    if rule["type"] == RULE_INTERVAL:
        return f"каждые {rule['n']} {'ч' if rule['unit'] == 'hours' else 'дн'}"
    if rule["type"] == RULE_WEEKLY:
        return "по " + ", ".join(names[d] for d in rule["weekdays"]) + f" в {rule['time']}"
    return f"каждое {rule['day']}-е число в {rule['time']}"


async def attach(session: AsyncSession, actor_id: int | None, task: Task, rule: dict, mode: str,
                 deadline_minutes: int | None, rotate: bool, rotation: list[int], ends_at: datetime | None) -> TaskSeries:
    """Сделать задачу цикличной (или обновить правило её серии). НЕ коммитит."""
    rule = validate(rule)
    if mode not in (SERIES_SCHEDULE, SERIES_AFTER_DONE):
        raise SeriesError("Неизвестный режим повтора")
    series = await session.get(TaskSeries, task.series_id) if task.series_id else None
    if series is None:
        series = TaskSeries(board_id=task.board_id, created_by=actor_id)
        session.add(series)
    series.rule, series.mode, series.deadline_minutes = rule, mode, deadline_minutes
    series.rotate, series.rotation, series.ends_at, series.active = rotate, rotation, ends_at, True
    series.template_task_id = task.id
    series.next_run_at = None if mode == SERIES_AFTER_DONE and task.completed_at is None else next_occurrence(rule, now())
    await session.flush()
    task.series_id = series.id
    tasks.history(session, task.id, actor_id, "series", rule=describe(rule), mode=mode)
    return series


async def detach(session: AsyncSession, actor_id: int | None, task: Task) -> None:
    if task.series_id:
        series = await session.get(TaskSeries, task.series_id)
        if series is not None:
            series.active = False
        tasks.history(session, task.id, actor_id, "series_off")


async def on_completed(session: AsyncSession, task: Task) -> None:
    """Задача серии выполнена: для режима after_done — запланировать следующую копию."""
    if not task.series_id:
        return
    series = await session.get(TaskSeries, task.series_id)
    if series is None or not series.active or series.mode != SERIES_AFTER_DONE or series.template_task_id != task.id:
        return
    series.next_run_at = next_occurrence(series.rule, now())


async def spawn(session: AsyncSession, series: TaskSeries) -> Task | None:
    """Очередная копия задачи серии (с шаблона — последней копии). НЕ коммитит."""
    template = await session.get(Task, series.template_task_id) if series.template_task_id else None
    if template is None:
        series.active = False
        return None
    t = now()
    if series.rotate and series.rotation:
        assignees = [series.rotation[series.rotation_index % len(series.rotation)]]
        series.rotation_index += 1
    else:
        assignees = await tasks.assignee_ids(session, template.id)
    checklist = [c.text for c in await session.scalars(
        select(ChecklistItem).where(ChecklistItem.task_id == template.id).order_by(ChecklistItem.position))]
    new = await tasks.create_task(
        session, None, board_id=template.board_id, title=template.title, description=template.description,
        priority=template.priority, label_ids=list(template.label_ids or []), assignees=assignees,
        deadline=t + timedelta(minutes=series.deadline_minutes) if series.deadline_minutes else None,
        deadline_hard=template.deadline_hard, estimate_minutes=template.estimate_minutes, checklist=checklist,
        series_id=series.id,
    )
    items = [
        {"kind": r.kind, "offset_minutes": r.offset_minutes, "interval_minutes": r.interval_minutes, "text": r.text}
        for r in await session.scalars(select(TaskReminder).where(TaskReminder.task_id == template.id))
        if r.kind != REM_AT
    ]
    if items:
        await reminders.set_reminders(session, new, items)
    else:
        await reminders.apply_defaults(session, new)
    series.template_task_id = new.id
    tasks.history(session, new.id, None, "spawned", series_id=series.id)
    return new


async def sweep(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Создать копии наступивших серий и объявить их в чате админов."""
    created = 0
    async with session_factory() as session:
        t = now()
        due = list(await session.scalars(
            select(TaskSeries).where(TaskSeries.active.is_(True), TaskSeries.next_run_at <= t).limit(20)
        ))
        for series in due:
            if series.ends_at and series.ends_at < t:
                series.active = False
                continue
            new = await spawn(session, series)
            if series.mode == SERIES_SCHEDULE:
                series.next_run_at = next_occurrence(series.rule, t)
            else:
                series.next_run_at = None  # следующая — после выполнения этой
            if new is not None:
                await session.flush()
                await reminders.announce(bot, session, new, "🔁 Новая задача по расписанию")
                created += 1
        await session.commit()
    return created
