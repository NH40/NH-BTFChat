from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import BotUser


async def get_or_create_user(session: AsyncSession, tg_user_id: int, username: str | None) -> BotUser:
    result = await session.execute(select(BotUser).where(BotUser.tg_user_id == tg_user_id))
    user = result.scalar_one_or_none()
    if user:
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user

    user = BotUser(tg_user_id=tg_user_id, username=username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
