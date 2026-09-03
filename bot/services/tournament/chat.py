from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import TournamentAdmin, TournamentChat


async def register_chat(
    session: AsyncSession, *, tg_chat_id: int, title: str | None, registered_by_tg_id: int
) -> TournamentChat:
    result = await session.execute(select(TournamentChat).where(TournamentChat.tg_chat_id == tg_chat_id))
    chat = result.scalar_one_or_none()
    if chat:
        chat.title = title
        await session.commit()
        return chat

    chat = TournamentChat(tg_chat_id=tg_chat_id, title=title, registered_by_tg_id=registered_by_tg_id)
    session.add(chat)
    await session.commit()
    return chat


async def get_registered_chat_id(session: AsyncSession) -> int | None:
    result = await session.execute(select(TournamentChat.tg_chat_id).limit(1))
    row = result.first()
    return row[0] if row else None


async def is_admin(session: AsyncSession, tg_user_id: int) -> bool:
    admin = await session.get(TournamentAdmin, tg_user_id)
    return admin is not None


async def has_any_admin(session: AsyncSession) -> bool:
    result = await session.execute(select(TournamentAdmin.tg_user_id).limit(1))
    return result.first() is not None


async def add_admin(session: AsyncSession, tg_user_id: int, added_by_tg_id: int) -> None:
    existing = await session.get(TournamentAdmin, tg_user_id)
    if existing:
        return
    session.add(TournamentAdmin(tg_user_id=tg_user_id, added_by_tg_id=added_by_tg_id))
    await session.commit()


async def remove_admin(session: AsyncSession, tg_user_id: int) -> None:
    existing = await session.get(TournamentAdmin, tg_user_id)
    if existing:
        await session.delete(existing)
        await session.commit()
