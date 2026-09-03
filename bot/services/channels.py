from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Channel


async def upsert_channel(
    session: AsyncSession,
    *,
    tg_chat_id: int,
    username: str | None,
    title: str | None,
    owner_id: int,
    bot_is_admin: bool,
) -> Channel:
    result = await session.execute(select(Channel).where(Channel.tg_chat_id == tg_chat_id))
    channel = result.scalar_one_or_none()
    if channel:
        channel.username = username
        channel.title = title
        channel.bot_is_admin = bot_is_admin
    else:
        channel = Channel(
            tg_chat_id=tg_chat_id,
            username=username,
            title=title,
            owner_user_id=owner_id,
            bot_is_admin=bot_is_admin,
        )
        session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def mark_bot_admin(session: AsyncSession, tg_chat_id: int, is_admin: bool) -> None:
    result = await session.execute(select(Channel).where(Channel.tg_chat_id == tg_chat_id))
    channel = result.scalar_one_or_none()
    if channel:
        channel.bot_is_admin = is_admin
        await session.commit()


async def get_channel_by_tg_id(session: AsyncSession, tg_chat_id: int) -> Channel | None:
    result = await session.execute(select(Channel).where(Channel.tg_chat_id == tg_chat_id))
    return result.scalar_one_or_none()
