from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import EloHistory, PlayerProfile, Season
from bot.services.tournament.elo import season_reset_rating


async def get_active_season(session: AsyncSession) -> Season | None:
    result = await session.execute(select(Season).where(Season.is_active.is_(True)))
    return result.scalar_one_or_none()


async def start_season(session: AsyncSession, name: str) -> Season:
    current = await get_active_season(session)
    if current:
        current.is_active = False
        current.ended_at = dt.datetime.utcnow()

    season = Season(name=name, is_active=True)
    session.add(season)
    await session.commit()
    return season


async def reset_all_ratings(session: AsyncSession) -> int:
    """Pulls every player's Elo back toward the baseline for a new season.

    Returns the number of players affected.
    """
    result = await session.execute(select(PlayerProfile))
    players = list(result.scalars().all())

    for player in players:
        before = player.elo
        after = season_reset_rating(before)
        if after != before:
            player.elo = after
            session.add(
                EloHistory(
                    player_id=player.id,
                    match_id=None,
                    elo_before=before,
                    elo_after=after,
                    reason="season_reset",
                )
            )

    await session.commit()
    return len(players)
