"""Операции над задачей, затрагивающие несколько доменов (задача + напоминания + серия).
Одна точка и для бота, и для Mini App. НЕ коммитят."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Task
from bot.services import reminders, series, tasks


async def after_status(session: AsyncSession, task: Task, status: str | None) -> None:
    if status == "completed":
        await series.on_completed(session, task)
    elif status == "reopened":
        await reminders.recompute(session, task, reset_deadline_based=True)


async def complete(session: AsyncSession, actor_id: int | None, task: Task) -> bool:
    if not await tasks.complete(session, actor_id, task):
        return False
    await series.on_completed(session, task)
    return True


async def move(session: AsyncSession, actor_id: int | None, task: Task, column_id: int, position: float | None = None) -> str | None:
    status = await tasks.move(session, actor_id, task, column_id, position)
    await after_status(session, task, status)
    return status


async def update(session: AsyncSession, actor_id: int | None, task: Task, changes: dict) -> None:
    if await tasks.update_task(session, actor_id, task, changes):
        await reminders.recompute(session, task, reset_deadline_based=True)
