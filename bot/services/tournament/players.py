from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import ELO_DEFAULT
from bot.db import PlayerProfile


async def get_or_create_player(
    session: AsyncSession, tg_user_id: int, display_name: str | None = None
) -> PlayerProfile:
    result = await session.execute(select(PlayerProfile).where(PlayerProfile.tg_user_id == tg_user_id))
    player = result.scalar_one_or_none()
    if player:
        if display_name and player.display_name != display_name:
            player.display_name = display_name
            await session.commit()
        return player

    player = PlayerProfile(tg_user_id=tg_user_id, display_name=display_name, elo=ELO_DEFAULT)
    session.add(player)
    await session.commit()
    return player


async def get_player_by_tg_id(session: AsyncSession, tg_user_id: int) -> PlayerProfile | None:
    result = await session.execute(select(PlayerProfile).where(PlayerProfile.tg_user_id == tg_user_id))
    return result.scalar_one_or_none()


async def set_judge_flag(session: AsyncSession, tg_user_id: int, is_judge: bool) -> PlayerProfile | None:
    player = await get_player_by_tg_id(session, tg_user_id)
    if player:
        player.is_judge = is_judge
        await session.commit()
    return player


async def list_judges(session: AsyncSession) -> list[PlayerProfile]:
    result = await session.execute(select(PlayerProfile).where(PlayerProfile.is_judge.is_(True)))
    return list(result.scalars().all())


async def leaderboard(session: AsyncSession, limit: int = 10) -> list[PlayerProfile]:
    result = await session.execute(select(PlayerProfile).order_by(PlayerProfile.elo.desc()).limit(limit))
    return list(result.scalars().all())


async def list_all_players(session: AsyncSession) -> list[PlayerProfile]:
    result = await session.execute(select(PlayerProfile))
    return list(result.scalars().all())
