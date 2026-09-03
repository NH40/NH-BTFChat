from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.constant import DEFAULT_BRACKET_SLOTS
from bot.db import Match, Tournament, TournamentSignup
from bot.services.tournament.matches import STATUS_COMPLETED as MATCH_STATUS_COMPLETED
from bot.services.tournament.matches import create_match

STATUS_REGISTRATION = "registration"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


async def create_tournament(
    session: AsyncSession,
    *,
    name: str,
    chat_id: int,
    created_by_tg_id: int,
    universe_id: int | None = None,
    season_id: int | None = None,
    slots: int = DEFAULT_BRACKET_SLOTS,
) -> Tournament:
    if slots < 2 or (slots & (slots - 1)) != 0:
        raise ValueError("slots must be a power of two (2, 4, 8, 16, ...)")

    tournament = Tournament(
        name=name,
        chat_id=chat_id,
        created_by_tg_id=created_by_tg_id,
        universe_id=universe_id,
        season_id=season_id,
        slots=slots,
        status=STATUS_REGISTRATION,
    )
    tournament.signups = []
    session.add(tournament)
    await session.commit()
    return tournament


async def get_tournament(session: AsyncSession, tournament_id: int) -> Tournament | None:
    result = await session.execute(
        select(Tournament)
        .options(selectinload(Tournament.signups))
        .where(Tournament.id == tournament_id)
    )
    return result.scalar_one_or_none()


async def join_tournament(session: AsyncSession, tournament: Tournament, player_id: int) -> TournamentSignup:
    if tournament.status != STATUS_REGISTRATION:
        raise ValueError("this tournament is not open for registration")
    if any(s.player_id == player_id for s in tournament.signups):
        raise ValueError("this player has already joined")
    if len(tournament.signups) >= tournament.slots:
        raise ValueError("tournament is full")

    signup = TournamentSignup(tournament_id=tournament.id, player_id=player_id)
    session.add(signup)
    tournament.signups.append(signup)
    await session.commit()
    return signup


def is_full(tournament: Tournament) -> bool:
    return len(tournament.signups) >= tournament.slots


async def start_bracket(
    session: AsyncSession, tournament: Tournament, *, rng: random.Random | None = None
) -> list[Match]:
    """Randomly seeds round-1 pairings once the bracket is full."""
    if tournament.status != STATUS_REGISTRATION:
        raise ValueError("tournament has already started")
    if not is_full(tournament):
        raise ValueError("tournament is not full yet")
    if tournament.universe_id is None:
        raise ValueError("tournament has no universe assigned")

    rng = rng or random.Random()
    player_ids = [s.player_id for s in tournament.signups]
    rng.shuffle(player_ids)

    matches = []
    for i in range(0, len(player_ids), 2):
        match = await create_match(
            session,
            universe_id=tournament.universe_id,
            player1_id=player_ids[i],
            player2_id=player_ids[i + 1],
            chat_id=tournament.chat_id,
            created_by_tg_id=tournament.created_by_tg_id,
            tournament_id=tournament.id,
            round_number=1,
        )
        matches.append(match)

    tournament.status = STATUS_IN_PROGRESS
    await session.commit()
    return matches


async def round_matches(session: AsyncSession, tournament_id: int, round_number: int) -> list[Match]:
    result = await session.execute(
        select(Match).where(Match.tournament_id == tournament_id, Match.round_number == round_number)
    )
    return list(result.scalars().all())


async def advance_round(
    session: AsyncSession, tournament: Tournament, round_number: int, *, rng: random.Random | None = None
) -> tuple[list[Match], int | None]:
    """Pairs up the winners of `round_number` into the next round.

    Returns (new_matches, champion_player_id). champion_player_id is set instead
    of new_matches when only one winner remains.
    """
    matches = await round_matches(session, tournament.id, round_number)
    if not matches:
        raise ValueError(f"no matches found for round {round_number}")
    if any(m.status != MATCH_STATUS_COMPLETED for m in matches):
        raise ValueError("not all matches in this round are finished yet")
    if any(m.winner_id is None for m in matches):
        raise ValueError("cannot advance a round that contains an undecided (drawn) match")

    winners = [m.winner_id for m in matches]

    if len(winners) == 1:
        tournament.status = STATUS_COMPLETED
        await session.commit()
        return [], winners[0]

    rng = rng or random.Random()
    rng.shuffle(winners)

    new_matches = []
    for i in range(0, len(winners), 2):
        match = await create_match(
            session,
            universe_id=tournament.universe_id,
            player1_id=winners[i],
            player2_id=winners[i + 1],
            chat_id=tournament.chat_id,
            created_by_tg_id=tournament.created_by_tg_id,
            tournament_id=tournament.id,
            round_number=round_number + 1,
        )
        new_matches.append(match)

    return new_matches, None
