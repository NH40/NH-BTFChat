"""Преобразование моделей в JSON для Mini App (пачками — без N+1)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db import Chat, ChecklistItem, Task, TaskAssignee, TaskComment, TgUser, TimeEntry
from bot.utils.time import now


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def user_out(u: TgUser | None, uid: int | None = None) -> dict | None:
    if u is None:
        return {"id": uid, "name": str(uid), "username": None} if uid else None
    return {"id": u.id, "name": u.display_name, "username": u.username}


async def tasks_out(session: AsyncSession, tasks: list[Task]) -> list[dict]:
    """Карточки задач для доски: исполнители, прогресс подзадач, комментарии, время."""
    if not tasks:
        return []
    ids = [t.id for t in tasks]
    assignees: dict[int, list[int]] = {}
    for tid, uid in (await session.execute(select(TaskAssignee.task_id, TaskAssignee.user_id).where(TaskAssignee.task_id.in_(ids)))).all():
        assignees.setdefault(tid, []).append(uid)
    checks = {tid: (total, done) for tid, total, done in (await session.execute(
        select(ChecklistItem.task_id, func.count(), func.count().filter(ChecklistItem.done))
        .where(ChecklistItem.task_id.in_(ids)).group_by(ChecklistItem.task_id))).all()}
    comments = dict((await session.execute(
        select(TaskComment.task_id, func.count()).where(TaskComment.task_id.in_(ids)).group_by(TaskComment.task_id))).all())
    spent = dict((await session.execute(
        select(TimeEntry.task_id, func.coalesce(func.sum(TimeEntry.seconds), 0))
        .where(TimeEntry.task_id.in_(ids)).group_by(TimeEntry.task_id))).all())
    running = {tid for (tid,) in (await session.execute(
        select(TimeEntry.task_id).where(TimeEntry.task_id.in_(ids), TimeEntry.ended_at.is_(None)))).all()}
    people_ids = {u for lst in assignees.values() for u in lst}
    people = {u.id: u for u in await session.scalars(select(TgUser).where(TgUser.id.in_(people_ids)))} if people_ids else {}
    t_now = now()
    out = []
    for t in tasks:
        total, done = checks.get(t.id, (0, 0))
        out.append({
            "id": t.id, "board_id": t.board_id, "column_id": t.column_id, "title": t.title,
            "priority": t.priority, "label_ids": list(t.label_ids or []), "position": t.position,
            "deadline": iso(t.deadline), "deadline_hard": t.deadline_hard, "start_at": iso(t.start_at),
            "overdue": bool(t.deadline and t.completed_at is None and t.deadline < t_now),
            "completed_at": iso(t.completed_at), "archived": t.archived, "series_id": t.series_id,
            "assignees": [user_out(people.get(u), u) for u in assignees.get(t.id, [])],
            "checklist": {"total": total, "done": done}, "comments": comments.get(t.id, 0),
            "time_seconds": int(spent.get(t.id, 0) or 0), "timer_running": t.id in running,
            "estimate_minutes": t.estimate_minutes,
        })
    return out


def aware(dt: datetime | None) -> datetime | None:
    """Время без пояса из формы Mini App считаем временем команды."""
    if dt is None:
        return None
    return dt.replace(tzinfo=settings.tz) if dt.tzinfo is None else dt


def chat_out(c: Chat) -> dict:
    return {"id": c.id, "title": c.title or str(c.id), "username": c.username, "type": c.type, "kind": c.kind,
            "bot_status": c.bot_status}
