from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import MatchVote


async def cast_vote(
    session: AsyncSession, *, match_id: int, voter_tg_id: int, voted_for_player_id: int
) -> MatchVote:
    result = await session.execute(
        select(MatchVote).where(MatchVote.match_id == match_id, MatchVote.voter_tg_id == voter_tg_id)
    )
    vote = result.scalar_one_or_none()
    if vote:
        vote.voted_for_player_id = voted_for_player_id
        await session.commit()
        return vote

    vote = MatchVote(match_id=match_id, voter_tg_id=voter_tg_id, voted_for_player_id=voted_for_player_id)
    session.add(vote)
    await session.commit()
    return vote


async def tally_votes(session: AsyncSession, match_id: int) -> dict[int, int]:
    result = await session.execute(select(MatchVote).where(MatchVote.match_id == match_id))
    votes = list(result.scalars().all())
    tally: dict[int, int] = {}
    for vote in votes:
        tally[vote.voted_for_player_id] = tally.get(vote.voted_for_player_id, 0) + 1
    return tally
