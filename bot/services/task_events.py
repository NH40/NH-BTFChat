from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import TaskEvent


async def log_event(
    session: AsyncSession,
    *,
    admin_chat_id: int,
    task_id: int,
    assignee_tg_id: int,
    assignee_name: str | None,
    event: str,
    on_time: bool | None,
    deadline: dt.datetime | None,
) -> None:
    session.add(
        TaskEvent(
            admin_chat_id=admin_chat_id,
            task_id=task_id,
            assignee_tg_id=assignee_tg_id,
            assignee_name=assignee_name,
            event=event,
            on_time=on_time,
            deadline=deadline,
        )
    )
    await session.commit()


async def delete_latest_event_for_task(session: AsyncSession, task_id: int) -> None:
    """Called on reopen, so undoing a done/missed mark doesn't double-count in stats."""
    result = await session.execute(
        select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at.desc()).limit(1)
    )
    event = result.scalar_one_or_none()
    if event:
        await session.delete(event)
        await session.commit()


async def get_stats(session: AsyncSession, admin_chat_id: int) -> list[dict]:
    result = await session.execute(
        select(TaskEvent).where(
            TaskEvent.admin_chat_id == admin_chat_id, TaskEvent.event.in_(("done", "missed"))
        )
    )
    events = result.scalars().all()

    stats: dict[int, dict] = {}
    for event in events:
        row = stats.setdefault(
            event.assignee_tg_id, {"name": event.assignee_name, "done": 0, "on_time": 0, "missed": 0}
        )
        if event.assignee_name:
            row["name"] = event.assignee_name
        if event.event == "done":
            row["done"] += 1
            if event.on_time:
                row["on_time"] += 1
        else:
            row["missed"] += 1

    return sorted(stats.values(), key=lambda row: (-row["done"], -row["on_time"], row["missed"]))
