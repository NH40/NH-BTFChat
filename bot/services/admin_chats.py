from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db import AdminChat, BotUser


async def upsert_admin_chat(
    session: AsyncSession, *, tg_chat_id: int, title: str | None, owner_id: int
) -> AdminChat:
    result = await session.execute(select(AdminChat).where(AdminChat.tg_chat_id == tg_chat_id))
    admin_chat = result.scalar_one_or_none()
    if admin_chat:
        admin_chat.title = title
    else:
        admin_chat = AdminChat(tg_chat_id=tg_chat_id, title=title, owner_user_id=owner_id)
        session.add(admin_chat)
    await session.commit()
    await session.refresh(admin_chat)
    return admin_chat


async def list_admin_chats_for_owner(session: AsyncSession, tg_user_id: int) -> list[AdminChat]:
    user_result = await session.execute(select(BotUser).where(BotUser.tg_user_id == tg_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return []

    result = await session.execute(select(AdminChat).where(AdminChat.owner_user_id == user.id))
    return list(result.scalars().all())


async def get_admin_chat(session: AsyncSession, admin_chat_id: int) -> AdminChat | None:
    result = await session.execute(
        select(AdminChat).options(selectinload(AdminChat.owner)).where(AdminChat.id == admin_chat_id)
    )
    return result.scalar_one_or_none()


async def get_admin_chat_by_tg_id(session: AsyncSession, tg_chat_id: int) -> AdminChat | None:
    result = await session.execute(
        select(AdminChat).options(selectinload(AdminChat.owner)).where(AdminChat.tg_chat_id == tg_chat_id)
    )
    return result.scalar_one_or_none()


async def delete_admin_chat(session: AsyncSession, admin_chat_id: int, tg_user_id: int) -> bool:
    admin_chat = await get_admin_chat(session, admin_chat_id)
    if not admin_chat or admin_chat.owner.tg_user_id != tg_user_id:
        return False
    await session.delete(admin_chat)
    await session.commit()
    return True
