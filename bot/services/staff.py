"""Команда и роли: владелец (OWNER_IDS + назначенные), старший, админ."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db import Staff, TgUser
from bot.db.models.users import ROLE_LEVEL, ROLE_OWNER


async def role_of(session: AsyncSession, user_id: int) -> str | None:
    """Роль в команде или None (не в команде). OWNER_IDS — всегда владельцы."""
    if user_id in settings.owner_ids:
        return ROLE_OWNER
    staff = await session.get(Staff, user_id)
    return staff.role if staff and staff.active else None


def at_least(role: str | None, need: str) -> bool:
    return role is not None and ROLE_LEVEL.get(role, 0) >= ROLE_LEVEL[need]


async def members(session: AsyncSession) -> list[tuple[Staff, TgUser]]:
    rows = await session.execute(
        select(Staff, TgUser).join(TgUser, TgUser.id == Staff.user_id).where(Staff.active.is_(True))
        .order_by(Staff.role.desc(), TgUser.first_name)
    )
    return list(rows.all())
