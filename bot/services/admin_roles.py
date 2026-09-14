from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import AdminRole


async def set_role(session: AsyncSession, admin_chat_id: int, tg_user_id: int, description: str) -> AdminRole:
    result = await session.execute(
        select(AdminRole).where(
            AdminRole.admin_chat_id == admin_chat_id, AdminRole.tg_user_id == tg_user_id
        )
    )
    role = result.scalar_one_or_none()
    if role:
        role.description = description
    else:
        role = AdminRole(admin_chat_id=admin_chat_id, tg_user_id=tg_user_id, description=description)
        session.add(role)
    await session.commit()
    await session.refresh(role)
    return role


async def get_role(session: AsyncSession, admin_chat_id: int, tg_user_id: int) -> AdminRole | None:
    result = await session.execute(
        select(AdminRole).where(
            AdminRole.admin_chat_id == admin_chat_id, AdminRole.tg_user_id == tg_user_id
        )
    )
    return result.scalar_one_or_none()
