from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import PendingAction


async def set_pending(session: AsyncSession, tg_user_id: int, action: str, payload: dict) -> None:
    existing = await session.get(PendingAction, tg_user_id)
    if existing:
        existing.action = action
        existing.payload = payload
    else:
        session.add(PendingAction(tg_user_id=tg_user_id, action=action, payload=payload))
    await session.commit()


async def get_pending(session: AsyncSession, tg_user_id: int) -> PendingAction | None:
    return await session.get(PendingAction, tg_user_id)


async def clear_pending(session: AsyncSession, tg_user_id: int) -> None:
    existing = await session.get(PendingAction, tg_user_id)
    if existing:
        await session.delete(existing)
        await session.commit()
