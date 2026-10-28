"""Я, команда и роли. Роли меняет владелец; старший может добавлять и убирать админов."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, bad, get_session, not_found, senior, viewer
from api.serializers import iso, user_out
from bot.config import settings
from bot.db import Staff, Task, TaskAssignee, TgUser
from bot.db.models.users import ROLE_ADMIN, ROLE_OWNER, ROLES
from bot.services import staff, tasks, users
from bot.utils.time import now

router = APIRouter(prefix="/api", tags=["team"])


@router.get("/me")
async def me(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    user = await users.ensure(session, v.id)
    t_now = now()
    base = select(func.count()).select_from(Task).join(TaskAssignee, TaskAssignee.task_id == Task.id).where(
        TaskAssignee.user_id == v.id, Task.completed_at.is_(None), Task.archived.is_(False))
    open_count = int(await session.scalar(base) or 0)
    overdue = int(await session.scalar(base.where(Task.deadline < t_now)) or 0)
    timer = await tasks.open_timer(session, v.id)
    timer_task = await session.get(Task, timer.task_id) if timer else None
    return {
        **user_out(user), "role": v.role, "is_senior": v.is_senior, "is_owner": v.is_owner,
        "timezone": settings.timezone, "open_tasks": open_count, "overdue_tasks": overdue,
        "timer": {"task_id": timer.task_id, "title": timer_task.title if timer_task else "", "started_at": iso(timer.started_at)} if timer else None,
    }


@router.get("/staff")
async def list_staff(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    """Вся команда (для выбора исполнителей): назначенные + владельцы из OWNER_IDS."""
    rows = await staff.members(session)
    out = [{**user_out(u), "role": s.role if u.id not in settings.owner_ids else ROLE_OWNER, "title": s.title,
            "notes": s.notes if v.is_senior else None, "fixed": u.id in settings.owner_ids} for s, u in rows]
    listed = {m["id"] for m in out}
    extra = await users.get_many(session, settings.owner_ids - listed)
    for uid in settings.owner_ids - listed:
        out.insert(0, {**user_out(extra.get(uid), uid), "role": ROLE_OWNER, "title": None, "notes": None, "fixed": True})
    order = {r: i for i, r in enumerate(ROLES)}
    return sorted(out, key=lambda m: (order.get(m["role"], 9), (m["name"] or "").lower()))


@router.get("/users/search")
async def search_users(q: str, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    """Люди, которых бот видел (писали ему или в чатах с ним) — для добавления в команду."""
    q = q.strip().lstrip("@")
    if not q:
        return []
    cond = [TgUser.username.ilike(f"%{q}%"), TgUser.first_name.ilike(f"%{q}%"), TgUser.last_name.ilike(f"%{q}%")]
    if q.isdigit():
        cond.append(TgUser.id == int(q))
    rows = await session.scalars(select(TgUser).where(or_(*cond)).order_by(TgUser.last_seen_at.desc()).limit(20))
    return [user_out(u) for u in rows]


class StaffIn(BaseModel):
    user: str = Field(min_length=1)  # id или @username
    role: str = ROLE_ADMIN
    title: str | None = Field(None, max_length=128)
    notes: str | None = None


def _check_role_change(v: Viewer, old_role: str | None, new_role: str | None) -> None:
    if new_role is not None and new_role not in ROLES:
        raise bad("Неизвестная роль")
    if v.is_owner:
        return
    # Старший управляет только админами.
    if (old_role not in (None, ROLE_ADMIN)) or (new_role not in (None, ROLE_ADMIN)):
        raise bad("Назначать старших и владельцев может только владелец")


@router.post("/staff")
async def add_staff(body: StaffIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    user = await users.resolve(session, body.user)
    if user is None:
        raise not_found("Пользователь не найден — пусть напишет боту /start или в чат с ботом")
    current = await session.get(Staff, user.id)
    _check_role_change(v, current.role if current and current.active else None, body.role)
    if current is None:
        session.add(Staff(user_id=user.id, role=body.role, title=body.title, notes=body.notes))
    else:
        current.role, current.title, current.notes, current.active = body.role, body.title, body.notes, True
    await session.commit()
    return {"id": user.id}


class StaffPatch(BaseModel):
    role: str | None = None
    title: str | None = Field(None, max_length=128)
    notes: str | None = None


@router.patch("/staff/{user_id}")
async def patch_staff(user_id: int, body: StaffPatch, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    if user_id in settings.owner_ids and body.role not in (None, ROLE_OWNER):
        raise bad("Роль владельцев из OWNER_IDS меняется только в .env")
    row = await session.get(Staff, user_id)
    if row is None:
        if user_id not in settings.owner_ids:
            raise not_found("Не в команде")
        await users.ensure(session, user_id)
        row = Staff(user_id=user_id, role=ROLE_OWNER)
        session.add(row)
    changes = body.model_dump(exclude_unset=True)
    if "role" in changes:
        _check_role_change(v, row.role, changes["role"])
    elif not v.is_owner and row.role != ROLE_ADMIN:
        raise bad("Старший может менять только админов")
    for key, value in changes.items():
        if value is not None or key != "role":
            setattr(row, key, value)
    await session.commit()
    return {"ok": True}


@router.delete("/staff/{user_id}")
async def remove_staff(user_id: int, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    if user_id in settings.owner_ids:
        raise bad("Владельца из OWNER_IDS убрать нельзя")
    if user_id == v.id:
        raise bad("Нельзя убрать самого себя")
    row = await session.get(Staff, user_id)
    if row is None or not row.active:
        raise not_found("Не в команде")
    _check_role_change(v, row.role, None)
    row.active = False
    await session.commit()
    return {"ok": True}
