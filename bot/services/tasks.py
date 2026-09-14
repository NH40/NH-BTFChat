from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db import AdminChat, Task


async def create_task(
    session: AsyncSession,
    *,
    admin_chat_id: int,
    created_by_tg_id: int,
    assignee_tg_id: int,
    assignee_name: str | None,
    title: str,
    deadline: dt.datetime | None,
    reminder_policy: str,
) -> Task:
    task = Task(
        admin_chat_id=admin_chat_id,
        created_by_tg_id=created_by_tg_id,
        assignee_tg_id=assignee_tg_id,
        assignee_name=assignee_name,
        title=title,
        deadline=deadline,
        reminder_policy=reminder_policy,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def set_task_message(session: AsyncSession, task_id: int, chat_message_id: int) -> None:
    task = await session.get(Task, task_id)
    if task:
        task.chat_message_id = chat_message_id
        await session.commit()


async def get_task(session: AsyncSession, task_id: int) -> Task | None:
    result = await session.execute(
        select(Task)
        .options(selectinload(Task.admin_chat).selectinload(AdminChat.owner))
        .where(Task.id == task_id)
    )
    return result.scalar_one_or_none()


async def list_open_tasks(session: AsyncSession, admin_chat_id: int) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(Task.admin_chat_id == admin_chat_id, Task.status == "open")
        .order_by(Task.deadline.is_(None), Task.deadline, Task.created_at)
    )
    return list(result.scalars().all())


async def mark_done(session: AsyncSession, task_id: int) -> Task | None:
    task = await session.get(Task, task_id)
    if not task:
        return None
    task.status = "done"
    task.completed_at = dt.datetime.utcnow()
    await session.commit()
    await session.refresh(task)
    return task


async def cancel_task(session: AsyncSession, task_id: int) -> Task | None:
    task = await session.get(Task, task_id)
    if not task:
        return None
    task.status = "cancelled"
    await session.commit()
    await session.refresh(task)
    return task


async def list_tasks_due_for_reminder(session: AsyncSession) -> list[Task]:
    result = await session.execute(
        select(Task)
        .options(selectinload(Task.admin_chat))
        .where(Task.status == "open", Task.deadline.is_not(None))
    )
    return list(result.scalars().all())


async def mark_pre_reminder_sent(session: AsyncSession, task_id: int) -> None:
    task = await session.get(Task, task_id)
    if task:
        task.pre_reminder_sent = True
        await session.commit()


async def mark_deadline_notified(session: AsyncSession, task_id: int, when: dt.datetime) -> None:
    task = await session.get(Task, task_id)
    if task:
        task.deadline_notified = True
        task.last_reminded_at = when
        await session.commit()


async def touch_last_reminded(session: AsyncSession, task_id: int, when: dt.datetime) -> None:
    task = await session.get(Task, task_id)
    if task:
        task.last_reminded_at = when
        await session.commit()
