"""Задачи: список доски, карточка, создание/правка, перенос, исполнители, подзадачи,
комментарии, учёт времени, напоминания, повтор. Каждая мутация — один commit."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, bad, get_bot, get_session, not_found, viewer
from api.serializers import aware, iso, tasks_out, user_out
from bot.db import (
    Board, ChecklistItem, Task, TaskAssignee, TaskComment, TaskHistory, TaskReminder, TaskSeries, TimeEntry,
)
from bot.services import reminders, series, tasks, users, workflow
from bot.utils.time import now

router = APIRouter(prefix="/api", tags=["tasks"])

DONE_VISIBLE_DAYS = 14  # выполненные задачи старше — только по фильтру «показать все»


# ---------------------------------------------------------------- доступ

async def _task(session: AsyncSession, task_id: int) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise not_found("Задача не найдена")
    return task


async def _can_edit(session: AsyncSession, v: Viewer, task: Task) -> bool:
    """Старший/владелец — любую; админ — свою (создал или исполнитель)."""
    if v.is_senior or task.created_by == v.id:
        return True
    return await session.get(TaskAssignee, (task.id, v.id)) is not None


async def _editable(session: AsyncSession, v: Viewer, task_id: int) -> Task:
    task = await _task(session, task_id)
    if not await _can_edit(session, v, task):
        raise bad("Менять задачу может её автор, исполнитель или старший")
    return task


# ---------------------------------------------------------------- чтение

@router.get("/boards/{board_id}/tasks")
async def board_tasks(board_id: int, show_done: bool = False, archived: bool = False, assignee: int | None = None,
                      q: str | None = None, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    stmt = select(Task).where(Task.board_id == board_id, Task.archived.is_(archived))
    if not show_done and not archived:
        stmt = stmt.where((Task.completed_at.is_(None)) | (Task.completed_at >= now() - timedelta(days=DONE_VISIBLE_DAYS)))
    if assignee:
        stmt = stmt.where(Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == assignee)))
    if q:
        stmt = stmt.where(Task.title.ilike(f"%{q.strip()}%"))
    rows = list(await session.scalars(stmt.order_by(Task.position).limit(1000)))
    return await tasks_out(session, rows)


@router.get("/tasks/mine")
async def my_tasks(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    rows = list(await session.scalars(
        select(Task).join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .where(TaskAssignee.user_id == v.id, Task.completed_at.is_(None), Task.archived.is_(False))
        .order_by(Task.deadline.is_(None), Task.deadline, Task.priority.desc()).limit(200)
    ))
    return await tasks_out(session, rows)


@router.get("/tasks/{task_id}")
async def task_detail(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _task(session, task_id)
    card = (await tasks_out(session, [task]))[0]
    checklist = list(await session.scalars(select(ChecklistItem).where(ChecklistItem.task_id == task.id).order_by(ChecklistItem.position)))
    comments = list(await session.scalars(select(TaskComment).where(TaskComment.task_id == task.id).order_by(TaskComment.created_at)))
    hist = list(await session.scalars(select(TaskHistory).where(TaskHistory.task_id == task.id).order_by(TaskHistory.created_at.desc()).limit(100)))
    rems = list(await session.scalars(select(TaskReminder).where(TaskReminder.task_id == task.id).order_by(TaskReminder.id)))
    entries = list(await session.scalars(select(TimeEntry).where(TimeEntry.task_id == task.id).order_by(TimeEntry.started_at.desc()).limit(50)))
    ser = await session.get(TaskSeries, task.series_id) if task.series_id else None
    people_ids = {c.user_id for c in comments} | {h.user_id for h in hist if h.user_id} | {e.user_id for e in entries}
    people_ids |= {c.assignee_id for c in checklist if c.assignee_id} | {task.created_by or 0, task.completed_by or 0}
    people_ids |= set(ser.rotation or []) if ser else set()
    people = await users.get_many(session, {p for p in people_ids if p})

    def who(uid: int | None):
        return user_out(people.get(uid), uid) if uid else None

    t_now = now()
    per_user: dict[int, int] = {}
    for e in entries:
        per_user[e.user_id] = per_user.get(e.user_id, 0) + (e.seconds if e.ended_at else int((t_now - e.started_at).total_seconds()))
    return {
        **card,
        "description": task.description, "created_at": iso(task.created_at), "created_by": who(task.created_by),
        "completed_by": who(task.completed_by), "can_edit": await _can_edit(session, v, task),
        "checklist_items": [{"id": c.id, "text": c.text, "done": c.done, "assignee": who(c.assignee_id),
                             "deadline": iso(c.deadline), "done_at": iso(c.done_at)} for c in checklist],
        "comment_list": [{"id": c.id, "user": who(c.user_id), "text": c.text, "created_at": iso(c.created_at)} for c in comments],
        "history": [{"id": h.id, "user": who(h.user_id), "action": h.action, "data": h.data, "created_at": iso(h.created_at)} for h in hist],
        "reminders": [{"id": r.id, "kind": r.kind, "offset_minutes": r.offset_minutes, "at": iso(r.at),
                       "interval_minutes": r.interval_minutes, "text": r.text, "next_at": iso(r.next_at),
                       "sent_count": r.sent_count, "active": r.active} for r in rems],
        "time_entries": [{"id": e.id, "user": who(e.user_id), "started_at": iso(e.started_at), "ended_at": iso(e.ended_at),
                          "seconds": e.seconds, "note": e.note} for e in entries],
        "time_by_user": [{"user": who(uid), "seconds": s} for uid, s in sorted(per_user.items(), key=lambda kv: -kv[1])],
        "series": None if ser is None or not ser.active else {
            "id": ser.id, "rule": ser.rule, "mode": ser.mode, "deadline_minutes": ser.deadline_minutes,
            "rotate": ser.rotate, "rotation": [who(u) for u in ser.rotation or []], "next_run_at": iso(ser.next_run_at),
            "ends_at": iso(ser.ends_at), "describe": series.describe(ser.rule),
        },
    }


# ---------------------------------------------------------------- создание и правка

class ReminderIn(BaseModel):
    kind: str
    offset_minutes: int | None = None
    at: datetime | None = None
    interval_minutes: int | None = None
    text: str | None = Field(None, max_length=512)


def _rem_items(items: list[ReminderIn]) -> list[dict]:
    return [{**r.model_dump(), "at": aware(r.at)} for r in items]


class TaskIn(BaseModel):
    board_id: int
    title: str = Field(min_length=1, max_length=256)
    column_id: int | None = None
    description: str | None = None
    priority: int = 1
    label_ids: list[int] = []
    assignees: list[int] = []
    deadline: datetime | None = None
    deadline_hard: bool = True
    start_at: datetime | None = None
    estimate_minutes: int | None = None
    checklist: list[str] = []
    reminders: list[ReminderIn] | None = None  # None — напоминания по умолчанию из настроек
    notify: bool = True  # объявить в чате админов с упоминанием исполнителей


@router.post("/tasks")
async def create_task(body: TaskIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    if await session.get(Board, body.board_id) is None:
        raise not_found("Доска не найдена")
    task = await tasks.create_task(
        session, v.id, board_id=body.board_id, title=body.title, column_id=body.column_id, description=body.description,
        priority=body.priority, label_ids=body.label_ids, assignees=body.assignees, deadline=aware(body.deadline),
        deadline_hard=body.deadline_hard, start_at=aware(body.start_at), estimate_minutes=body.estimate_minutes,
        checklist=body.checklist,
    )
    if body.reminders is None:
        await reminders.apply_defaults(session, task)
    else:
        await reminders.set_reminders(session, task, _rem_items(body.reminders))
    await session.commit()
    if body.notify and body.assignees:
        await reminders.announce(get_bot(), session, task, "🆕 Новая задача")
    return {"id": task.id}


class TaskPatch(BaseModel):
    title: str | None = Field(None, max_length=256)
    description: str | None = None
    priority: int | None = None
    label_ids: list[int] | None = None
    deadline: datetime | None = None
    deadline_hard: bool | None = None
    start_at: datetime | None = None
    estimate_minutes: int | None = None


@router.patch("/tasks/{task_id}")
async def patch_task(task_id: int, body: TaskPatch, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    changes = body.model_dump(exclude_unset=True)
    for key in ("deadline", "start_at"):
        if key in changes:
            changes[key] = aware(changes[key])
    if "priority" in changes and changes["priority"] is not None:
        changes["priority"] = max(0, min(3, changes["priority"]))
    await workflow.update(session, v.id, task, changes)
    await session.commit()
    return {"ok": True}


class AssigneesIn(BaseModel):
    user_ids: list[int]
    notify: bool = True


@router.put("/tasks/{task_id}/assignees")
async def put_assignees(task_id: int, body: AssigneesIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    before = set(await tasks.assignee_ids(session, task.id))
    await tasks.set_assignees(session, v.id, task, body.user_ids)
    await session.commit()
    added = set(body.user_ids) - before
    if body.notify and added and task.completed_at is None:
        people = await users.get_many(session, added)
        names = ", ".join(u.display_name for u in people.values()) or "—"
        await reminders.announce(get_bot(), session, task, "👤 Назначена задача", f"Назначены: {names}")
    return {"ok": True}


class MoveIn(BaseModel):
    column_id: int
    position: float | None = None


@router.post("/tasks/{task_id}/move")
async def move_task(task_id: int, body: MoveIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    status = await workflow.move(session, v.id, task, body.column_id, body.position)
    await session.commit()
    return {"status": status}


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    if not await workflow.complete(session, v.id, task):
        raise bad("Задача уже выполнена")
    await session.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/take")
async def take_task(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _task(session, task_id)
    if task.completed_at is not None:
        raise bad("Задача уже выполнена")
    await tasks.take(session, v.id, task)
    await session.commit()
    return {"ok": True}


class ArchiveIn(BaseModel):
    archived: bool


@router.post("/tasks/{task_id}/archive")
async def archive_task(task_id: int, body: ArchiveIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    task.archived = body.archived
    tasks.history(session, task.id, v.id, "archived" if body.archived else "unarchived")
    await reminders.recompute(session, task)
    await session.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _task(session, task_id)
    if not (v.is_senior or task.created_by == v.id):
        raise bad("Удалить задачу может автор или старший")
    if task.series_id:
        await series.detach(session, v.id, task)
    await session.delete(task)
    await session.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/ping")
async def ping_task(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    """Напомнить исполнителям прямо сейчас (сообщение в чат админов)."""
    task = await _task(session, task_id)
    if not await reminders.announce(get_bot(), session, task, "🔔 Напоминание", f"Пинг от {(await users.ensure(session, v.id)).display_name}"):
        raise bad("Чат админов не задан — выберите его в разделе «Чаты»")
    tasks.history(session, task.id, v.id, "pinged")
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- подзадачи

class ChecklistIn(BaseModel):
    text: str = Field(min_length=1, max_length=512)
    assignee_id: int | None = None
    deadline: datetime | None = None


@router.post("/tasks/{task_id}/checklist")
async def add_checklist(task_id: int, body: ChecklistIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    item = await tasks.add_checklist_item(session, v.id, task, body.text, body.assignee_id, aware(body.deadline))
    await session.commit()
    return {"id": item.id}


class ChecklistPatch(BaseModel):
    done: bool | None = None
    text: str | None = Field(None, max_length=512)
    assignee_id: int | None = None
    deadline: datetime | None = None


async def _item(session: AsyncSession, v: Viewer, item_id: int) -> ChecklistItem:
    item = await session.get(ChecklistItem, item_id)
    if item is None:
        raise not_found("Подзадача не найдена")
    task = await _task(session, item.task_id)
    if not (await _can_edit(session, v, task) or item.assignee_id == v.id):
        raise bad("Нет доступа к подзадаче")
    return item


@router.patch("/checklist/{item_id}")
async def patch_checklist(item_id: int, body: ChecklistPatch, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    item = await _item(session, v, item_id)
    changes = body.model_dump(exclude_unset=True)
    if "done" in changes and changes["done"] is not None and changes["done"] != item.done:
        await tasks.toggle_checklist_item(session, v.id, item, changes["done"])
    if changes.get("text"):
        item.text = changes["text"].strip()[:512]
    if "assignee_id" in changes:
        item.assignee_id = changes["assignee_id"]
    if "deadline" in changes:
        item.deadline = aware(changes["deadline"])
    await session.commit()
    return {"ok": True}


@router.delete("/checklist/{item_id}")
async def delete_checklist(item_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    item = await _item(session, v, item_id)
    tasks.history(session, item.task_id, v.id, "subtask_removed", text=item.text)
    await session.delete(item)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- комментарии

class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/tasks/{task_id}/comments")
async def add_comment(task_id: int, body: CommentIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _task(session, task_id)
    comment = await tasks.add_comment(session, v.id, task, body.text)
    await session.commit()
    return {"id": comment.id}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    comment = await session.get(TaskComment, comment_id)
    if comment is None:
        raise not_found()
    if comment.user_id != v.id and not v.is_senior:
        raise bad("Удалить можно только свой комментарий")
    await session.delete(comment)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- учёт времени

@router.get("/timer")
async def my_timer(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    entry = await tasks.open_timer(session, v.id)
    if entry is None:
        return None
    task = await session.get(Task, entry.task_id)
    return {"task_id": entry.task_id, "title": task.title if task else "", "started_at": iso(entry.started_at)}


@router.post("/tasks/{task_id}/timer/start")
async def start_timer(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _task(session, task_id)
    if task.completed_at is not None:
        raise bad("Задача уже выполнена")
    await tasks.start_timer(session, v.id, task)
    await session.commit()
    return {"ok": True}


@router.post("/timer/stop")
async def stop_timer(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    entry = await tasks.stop_timer(session, v.id)
    await session.commit()
    return {"seconds": entry.seconds if entry else 0}


class TimeIn(BaseModel):
    minutes: int = Field(gt=0, le=24 * 60)
    note: str | None = Field(None, max_length=256)


@router.post("/tasks/{task_id}/time")
async def add_time(task_id: int, body: TimeIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _task(session, task_id)
    await tasks.add_manual_time(session, v.id, task, body.minutes, body.note)
    await session.commit()
    return {"ok": True}


@router.delete("/time/{entry_id}")
async def delete_time(entry_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    entry = await session.get(TimeEntry, entry_id)
    if entry is None:
        raise not_found()
    if entry.user_id != v.id and not v.is_senior:
        raise bad("Удалить можно только своё время")
    await session.delete(entry)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- напоминания и повтор

class RemindersIn(BaseModel):
    items: list[ReminderIn]


@router.put("/tasks/{task_id}/reminders")
async def put_reminders(task_id: int, body: RemindersIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    await reminders.set_reminders(session, task, _rem_items(body.items))
    tasks.history(session, task.id, v.id, "reminders", count=len(body.items))
    await session.commit()
    return {"ok": True}


class SeriesIn(BaseModel):
    rule: dict
    mode: str = "schedule"
    deadline_minutes: int | None = None
    rotate: bool = False
    rotation: list[int] = []
    ends_at: datetime | None = None


@router.put("/tasks/{task_id}/series")
async def put_series(task_id: int, body: SeriesIn, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    await series.attach(session, v.id, task, body.rule, body.mode, body.deadline_minutes, body.rotate, body.rotation,
                        aware(body.ends_at))
    await session.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}/series")
async def delete_series(task_id: int, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    task = await _editable(session, v, task_id)
    await series.detach(session, v.id, task)
    await session.commit()
    return {"ok": True}


@router.get("/series")
async def list_series(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    """Все активные повторы — обзор «что и когда появится»."""
    rows = list(await session.scalars(select(TaskSeries).where(TaskSeries.active.is_(True)).order_by(TaskSeries.next_run_at)))
    titles = dict((await session.execute(
        select(Task.id, Task.title).where(Task.id.in_([s.template_task_id for s in rows if s.template_task_id])))).all()) if rows else {}
    return [{"id": s.id, "board_id": s.board_id, "task_id": s.template_task_id, "title": titles.get(s.template_task_id, "—"),
             "describe": series.describe(s.rule), "mode": s.mode, "next_run_at": iso(s.next_run_at)} for s in rows]


@router.post("/tasks/bulk-delete-done")
async def purge_done(board_id: int, older_days: int = 30, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    """Архивировать выполненные задачи доски старше N дней (только старшие)."""
    if not v.is_senior:
        raise bad("Только для старших")
    border = now() - timedelta(days=max(1, older_days))
    ids = list(await session.scalars(select(Task.id).where(Task.board_id == board_id, Task.completed_at < border, Task.archived.is_(False))))
    if ids:
        await session.execute(delete(TaskReminder).where(TaskReminder.task_id.in_(ids)))
        for task in await session.scalars(select(Task).where(Task.id.in_(ids))):
            task.archived = True
    await session.commit()
    return {"archived": len(ids)}
