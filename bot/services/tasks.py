"""Задачи команды: доски, колонки, задачи, исполнители, подзадачи, комментарии, учёт времени.

Все функции НЕ коммитят — коммитит вызывающий (хендлер бота или роутер API) один раз за
операцию. Каждое изменение задачи пишет строку в `task_history`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import (
    Board, BoardColumn, ChecklistItem, Label, Task, TaskAssignee, TaskComment, TaskHistory, TaskReminder, TimeEntry,
)
from bot.utils.time import now

DEFAULT_COLUMNS = (("Бэклог", False), ("В работе", False), ("На проверке", False), ("Готово", True))


class TaskError(Exception):
    pass


def history(session: AsyncSession, task_id: int, user_id: int | None, action: str, **data) -> None:
    session.add(TaskHistory(task_id=task_id, user_id=user_id, action=action, data=data))


# ---------------------------------------------------------------- доски и колонки

async def ensure_default_board(session: AsyncSession) -> None:
    if await session.scalar(select(func.count()).select_from(Board)):
        return
    await create_board(session, "Основная", None)


async def create_board(session: AsyncSession, name: str, actor_id: int | None, color: str = "#5b8cff",
                       columns: tuple = DEFAULT_COLUMNS) -> Board:
    pos = int(await session.scalar(select(func.coalesce(func.max(Board.position), -1))) or -1) + 1
    board = Board(name=name.strip()[:128] or "Доска", color=color, position=pos, created_by=actor_id)
    session.add(board)
    await session.flush()
    for i, (col_name, done) in enumerate(columns):
        session.add(BoardColumn(board_id=board.id, name=col_name, position=i, is_done=done))
    await session.flush()
    return board


async def columns(session: AsyncSession, board_id: int) -> list[BoardColumn]:
    return list(await session.scalars(select(BoardColumn).where(BoardColumn.board_id == board_id).order_by(BoardColumn.position)))


async def first_open_column(session: AsyncSession, board_id: int) -> BoardColumn:
    cols = await columns(session, board_id)
    if not cols:
        raise TaskError("У доски нет колонок")
    return next((c for c in cols if not c.is_done), cols[0])


async def done_column(session: AsyncSession, board_id: int) -> BoardColumn | None:
    return next((c for c in await columns(session, board_id) if c.is_done), None)


async def delete_column(session: AsyncSession, column: BoardColumn) -> None:
    """Колонку можно удалить, только если она не последняя; задачи уходят в первую открытую."""
    cols = await columns(session, column.board_id)
    rest = [c for c in cols if c.id != column.id]
    if not rest:
        raise TaskError("Нельзя удалить последнюю колонку")
    target = next((c for c in rest if not c.is_done), rest[0])
    await session.execute(update(Task).where(Task.column_id == column.id).values(column_id=target.id))
    await session.delete(column)


# ---------------------------------------------------------------- задачи

async def _next_position(session: AsyncSession, column_id: int) -> float:
    return float(await session.scalar(select(func.coalesce(func.max(Task.position), 0.0)).where(Task.column_id == column_id)) or 0) + 1.0


async def create_task(session: AsyncSession, actor_id: int | None, *, board_id: int, title: str,
                      column_id: int | None = None, description: str | None = None, priority: int = 1,
                      label_ids: list[int] | None = None, assignees: list[int] | None = None,
                      deadline: datetime | None = None, deadline_hard: bool = True, start_at: datetime | None = None,
                      estimate_minutes: int | None = None, checklist: list[str] | None = None,
                      series_id: int | None = None) -> Task:
    if not title.strip():
        raise TaskError("Пустое название задачи")
    if column_id is None:
        column_id = (await first_open_column(session, board_id)).id
    task = Task(
        board_id=board_id, column_id=column_id, title=title.strip()[:256], description=description,
        priority=max(0, min(3, priority)), label_ids=label_ids or [], deadline=deadline, deadline_hard=deadline_hard,
        start_at=start_at, estimate_minutes=estimate_minutes, created_by=actor_id, series_id=series_id,
        position=await _next_position(session, column_id),
    )
    session.add(task)
    await session.flush()
    for uid in dict.fromkeys(assignees or []):
        session.add(TaskAssignee(task_id=task.id, user_id=uid))
    for i, text in enumerate(checklist or []):
        if text.strip():
            session.add(ChecklistItem(task_id=task.id, text=text.strip()[:512], position=i))
    history(session, task.id, actor_id, "created", title=task.title)
    await session.flush()
    return task


_EDITABLE = {"title", "description", "priority", "label_ids", "deadline", "deadline_hard", "start_at", "estimate_minutes"}


async def update_task(session: AsyncSession, actor_id: int | None, task: Task, changes: dict) -> bool:
    """Применить изменения полей. → поменялся ли срок (нужно пересчитать напоминания)."""
    deadline_changed = False
    for field, value in changes.items():
        if field not in _EDITABLE:
            continue
        old = getattr(task, field)
        if field == "title":
            value = (value or "").strip()[:256]
            if not value:
                raise TaskError("Пустое название задачи")
        if old == value:
            continue
        setattr(task, field, value)
        history(session, task.id, actor_id, "changed", field=field,
                old=old.isoformat() if isinstance(old, datetime) else old,
                new=value.isoformat() if isinstance(value, datetime) else value)
        if field == "deadline":
            deadline_changed = True
    return deadline_changed


async def set_assignees(session: AsyncSession, actor_id: int | None, task: Task, user_ids: list[int]) -> None:
    current = set(await session.scalars(select(TaskAssignee.user_id).where(TaskAssignee.task_id == task.id)))
    wanted = set(user_ids)
    for uid in current - wanted:
        await session.execute(delete(TaskAssignee).where(TaskAssignee.task_id == task.id, TaskAssignee.user_id == uid))
    for uid in wanted - current:
        session.add(TaskAssignee(task_id=task.id, user_id=uid))
    if current != wanted:
        history(session, task.id, actor_id, "assignees", added=sorted(wanted - current), removed=sorted(current - wanted))


async def assignee_ids(session: AsyncSession, task_id: int) -> list[int]:
    return list(await session.scalars(select(TaskAssignee.user_id).where(TaskAssignee.task_id == task_id)))


async def take(session: AsyncSession, user_id: int, task: Task) -> None:
    """«Взял в работу»: отмечает исполнителя (добавляет, если его не было) и двигает из бэклога."""
    row = await session.get(TaskAssignee, (task.id, user_id))
    if row is None:
        session.add(TaskAssignee(task_id=task.id, user_id=user_id, taken_at=now()))
    else:
        row.taken_at = now()
    cols = await columns(session, task.board_id)
    current = next((c for c in cols if c.id == task.column_id), None)
    if current is not None and current.position == 0 and len(cols) > 1 and not cols[1].is_done:
        task.column_id = cols[1].id
    history(session, task.id, user_id, "taken")


async def move(session: AsyncSession, actor_id: int | None, task: Task, column_id: int, position: float | None = None) -> str | None:
    """Перенос в колонку. → 'completed' / 'reopened' / None — что произошло со статусом."""
    column = await session.get(BoardColumn, column_id)
    if column is None or column.board_id != task.board_id:
        raise TaskError("Колонка не на этой доске")
    old_column = await session.get(BoardColumn, task.column_id)
    task.column_id = column.id
    task.position = position if position is not None else await _next_position(session, column.id)
    if old_column is None or old_column.id != column.id:
        history(session, task.id, actor_id, "moved", to=column.name, frm=old_column.name if old_column else None)
    if column.is_done and task.completed_at is None:
        await _mark_completed(session, actor_id, task)
        return "completed"
    if not column.is_done and task.completed_at is not None:
        task.completed_at = None
        task.completed_by = None
        history(session, task.id, actor_id, "reopened")
        return "reopened"
    return None


async def _mark_completed(session: AsyncSession, actor_id: int | None, task: Task) -> None:
    task.completed_at = now()
    task.completed_by = actor_id
    await stop_timers_for_task(session, task.id)
    await session.execute(update(TaskReminder).where(TaskReminder.task_id == task.id).values(active=False))
    history(session, task.id, actor_id, "completed",
            on_time=None if task.deadline is None else task.completed_at <= task.deadline)


async def complete(session: AsyncSession, actor_id: int | None, task: Task) -> bool:
    """Выполнить (перенос в колонку «готово» доски). → False, если уже выполнена."""
    if task.completed_at is not None:
        return False
    done = await done_column(session, task.board_id)
    if done is None:
        await _mark_completed(session, actor_id, task)
    else:
        await move(session, actor_id, task, done.id)
    return True


# ---------------------------------------------------------------- подзадачи и комментарии

async def add_checklist_item(session: AsyncSession, actor_id: int | None, task: Task, text: str,
                             assignee_id: int | None = None, deadline: datetime | None = None) -> ChecklistItem:
    pos = int(await session.scalar(select(func.coalesce(func.max(ChecklistItem.position), -1)).where(ChecklistItem.task_id == task.id)) or -1) + 1
    item = ChecklistItem(task_id=task.id, text=text.strip()[:512], position=pos, assignee_id=assignee_id, deadline=deadline)
    session.add(item)
    history(session, task.id, actor_id, "subtask_added", text=item.text)
    await session.flush()
    return item


async def toggle_checklist_item(session: AsyncSession, actor_id: int | None, item: ChecklistItem, done: bool) -> None:
    item.done = done
    item.done_by = actor_id if done else None
    item.done_at = now() if done else None
    history(session, item.task_id, actor_id, "subtask_done" if done else "subtask_undone", text=item.text)


async def add_comment(session: AsyncSession, user_id: int, task: Task, text: str) -> TaskComment:
    if not text.strip():
        raise TaskError("Пустой комментарий")
    comment = TaskComment(task_id=task.id, user_id=user_id, text=text.strip()[:4000])
    session.add(comment)
    await session.flush()
    return comment


# ---------------------------------------------------------------- учёт времени

async def open_timer(session: AsyncSession, user_id: int) -> TimeEntry | None:
    return await session.scalar(select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.ended_at.is_(None)).limit(1))


def _close(entry: TimeEntry) -> None:
    entry.ended_at = now()
    entry.seconds = max(0, int((entry.ended_at - entry.started_at).total_seconds()))


async def start_timer(session: AsyncSession, user_id: int, task: Task) -> TimeEntry:
    """Запустить таймер по задаче (идущий по другой задаче — останавливается)."""
    current = await open_timer(session, user_id)
    if current is not None:
        if current.task_id == task.id:
            return current
        _close(current)
    entry = TimeEntry(task_id=task.id, user_id=user_id)
    session.add(entry)
    await session.flush()
    return entry


async def stop_timer(session: AsyncSession, user_id: int) -> TimeEntry | None:
    current = await open_timer(session, user_id)
    if current is not None:
        _close(current)
        history(session, current.task_id, user_id, "time", seconds=current.seconds)
    return current


async def stop_timers_for_task(session: AsyncSession, task_id: int) -> None:
    for entry in await session.scalars(select(TimeEntry).where(TimeEntry.task_id == task_id, TimeEntry.ended_at.is_(None))):
        _close(entry)


async def add_manual_time(session: AsyncSession, user_id: int, task: Task, minutes: int, note: str | None = None) -> TimeEntry:
    if minutes <= 0:
        raise TaskError("Время должно быть больше 0")
    end = now()
    entry = TimeEntry(task_id=task.id, user_id=user_id, started_at=end, ended_at=end, seconds=minutes * 60, note=note)
    session.add(entry)
    history(session, task.id, user_id, "time", seconds=minutes * 60, manual=True)
    await session.flush()
    return entry


async def labels(session: AsyncSession, board_id: int) -> list[Label]:
    return list(await session.scalars(select(Label).where(Label.board_id == board_id).order_by(Label.id)))
