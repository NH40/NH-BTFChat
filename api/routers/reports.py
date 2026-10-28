"""Отчёты по команде за период: выполнено, в срок / с опозданием, просрочено сейчас,
затраченное время, по дням. Всё агрегируется в SQL."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, get_session, viewer
from api.serializers import user_out
from bot.config import settings
from bot.db import Task, TaskAssignee, TimeEntry
from bot.services import users
from bot.utils.time import now

router = APIRouter(prefix="/api", tags=["reports"])


def _period(days: int, start: date | None, end: date | None) -> tuple[datetime, datetime]:
    tz = settings.tz
    if start and end:
        return datetime.combine(start, time.min, tz), datetime.combine(end + timedelta(days=1), time.min, tz)
    today = now().astimezone(tz).date()
    return datetime.combine(today - timedelta(days=max(1, days) - 1), time.min, tz), datetime.combine(today + timedelta(days=1), time.min, tz)


@router.get("/reports")
async def report(days: int = 7, start: date | None = None, end: date | None = None, board_id: int | None = None,
                 v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    frm, to = _period(days, start, end)
    t_now = now()
    board_cond = [Task.board_id == board_id] if board_id else []

    on_time = case((Task.deadline.is_(None), None), (Task.completed_at <= Task.deadline, 1), else_=0)
    done_rows = (await session.execute(
        select(TaskAssignee.user_id, func.count(Task.id), func.count(on_time).filter(on_time == 1),
               func.count(on_time).filter(on_time == 0),
               func.avg(func.extract("epoch", Task.completed_at - Task.created_at)))
        .join(Task, Task.id == TaskAssignee.task_id)
        .where(Task.completed_at >= frm, Task.completed_at < to, *board_cond)
        .group_by(TaskAssignee.user_id)
    )).all()
    open_rows = (await session.execute(
        select(TaskAssignee.user_id, func.count(Task.id), func.count(Task.id).filter(Task.deadline < t_now))
        .join(Task, Task.id == TaskAssignee.task_id)
        .where(Task.completed_at.is_(None), Task.archived.is_(False), *board_cond)
        .group_by(TaskAssignee.user_id)
    )).all()
    time_q = select(TimeEntry.user_id, func.coalesce(func.sum(TimeEntry.seconds), 0)).where(
        TimeEntry.ended_at >= frm, TimeEntry.ended_at < to)
    if board_id:
        time_q = time_q.join(Task, Task.id == TimeEntry.task_id).where(Task.board_id == board_id)
    time_rows = (await session.execute(time_q.group_by(TimeEntry.user_id))).all()

    stats: dict[int, dict] = {}

    def row(uid: int) -> dict:
        return stats.setdefault(uid, {"completed": 0, "on_time": 0, "late": 0, "avg_hours": None,
                                      "open": 0, "overdue": 0, "seconds": 0})

    for uid, total, ok, late, avg in done_rows:
        r = row(uid)
        r.update(completed=total, on_time=ok, late=late, avg_hours=round(float(avg) / 3600, 1) if avg else None)
    for uid, total, overdue in open_rows:
        row(uid).update(open=total, overdue=overdue)
    for uid, seconds in time_rows:
        row(uid)["seconds"] = int(seconds or 0)
    people = await users.get_many(session, set(stats))
    members = []
    for uid, r in stats.items():
        with_deadline = r["on_time"] + r["late"]
        members.append({"user": user_out(people.get(uid), uid), **r,
                        "on_time_pct": round(100 * r["on_time"] / with_deadline) if with_deadline else None})
    members.sort(key=lambda m: (-m["completed"], -m["seconds"]))

    local_day = cast(func.timezone(settings.timezone, Task.completed_at), Date)
    per_day = dict((await session.execute(
        select(local_day, func.count()).where(Task.completed_at >= frm, Task.completed_at < to, *board_cond).group_by(local_day)
    )).all())
    created_day = cast(func.timezone(settings.timezone, Task.created_at), Date)
    created = dict((await session.execute(
        select(created_day, func.count()).where(Task.created_at >= frm, Task.created_at < to, *board_cond).group_by(created_day)
    )).all())
    days_list = []
    d = frm.date()
    while d < to.date():
        days_list.append({"date": d.isoformat(), "completed": per_day.get(d, 0), "created": created.get(d, 0)})
        d += timedelta(days=1)

    totals = {
        "completed": sum(m["completed"] for m in members), "on_time": sum(m["on_time"] for m in members),
        "late": sum(m["late"] for m in members), "seconds": sum(m["seconds"] for m in members),
        "open": int(await session.scalar(select(func.count()).select_from(Task).where(
            Task.completed_at.is_(None), Task.archived.is_(False), *board_cond)) or 0),
        "overdue": int(await session.scalar(select(func.count()).select_from(Task).where(
            Task.completed_at.is_(None), Task.archived.is_(False), Task.deadline < t_now, *board_cond)) or 0),
    }
    return {"from": frm.date().isoformat(), "to": (to - timedelta(days=1)).date().isoformat(),
            "totals": totals, "members": members, "days": days_list}
