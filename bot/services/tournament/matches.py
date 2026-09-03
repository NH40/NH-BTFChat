from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.constant import (
    BAN_COUNT_PER_PLAYER,
    FINAL_STATEMENT_P1_MINUTES,
    FINAL_STATEMENT_P2_MINUTES,
    MIN_JUDGES_PER_MATCH,
    PREP_MAX_HOURS,
    ROUND1_MINUTES_PER_PLAYER,
    ROUND2_MINUTES_PER_PLAYER,
    ROUND3_MINUTES_PER_PLAYER,
    VERDICT_MINUTES,
)
from bot.db import Character, EloHistory, Match, MatchBan, MatchJudge, MatchPick, MatchScore, PlayerProfile
from bot.services.tournament import draft, scoring
from bot.services.tournament.elo import update_ratings

# --- match status flow ---
STATUS_BAN_PHASE = "ban_phase"
STATUS_PREP = "prep"
STATUS_ROUND_1 = "round_1"
STATUS_ROUND_2 = "round_2"
STATUS_ROUND_3 = "round_3"
STATUS_FINAL_STATEMENT = "final_statement"
STATUS_JUDGING = "judging"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

FLOW_ORDER = [
    STATUS_BAN_PHASE,
    STATUS_PREP,
    STATUS_ROUND_1,
    STATUS_ROUND_2,
    STATUS_ROUND_3,
    STATUS_FINAL_STATEMENT,
    STATUS_JUDGING,
    STATUS_COMPLETED,
]

_TIMED_PHASE_MINUTES = {
    STATUS_ROUND_1: ROUND1_MINUTES_PER_PLAYER * 2,
    STATUS_ROUND_2: ROUND2_MINUTES_PER_PLAYER * 2,
    STATUS_ROUND_3: ROUND3_MINUTES_PER_PLAYER * 2,
    STATUS_FINAL_STATEMENT: FINAL_STATEMENT_P1_MINUTES + FINAL_STATEMENT_P2_MINUTES,
    STATUS_JUDGING: VERDICT_MINUTES,
}


async def create_match(
    session: AsyncSession,
    *,
    universe_id: int,
    player1_id: int,
    player2_id: int,
    chat_id: int,
    created_by_tg_id: int,
    tournament_id: int | None = None,
    round_number: int | None = None,
    prep_hours: int = PREP_MAX_HOURS,
) -> Match:
    if player1_id == player2_id:
        raise ValueError("a player cannot be matched against themselves")
    if not 1 <= prep_hours <= PREP_MAX_HOURS:
        raise ValueError(f"prep_hours must be between 1 and {PREP_MAX_HOURS}")

    match = Match(
        universe_id=universe_id,
        player1_id=player1_id,
        player2_id=player2_id,
        chat_id=chat_id,
        created_by_tg_id=created_by_tg_id,
        tournament_id=tournament_id,
        round_number=round_number,
        status=STATUS_BAN_PHASE,
    )
    match.bans = []
    match.picks = []
    match.judges = []
    match.scores = []
    match.votes = []
    session.add(match)
    await session.commit()
    return match


async def get_match(session: AsyncSession, match_id: int) -> Match | None:
    result = await session.execute(
        select(Match)
        .options(
            selectinload(Match.bans),
            selectinload(Match.picks),
            selectinload(Match.judges),
            selectinload(Match.scores),
            selectinload(Match.votes),
        )
        .where(Match.id == match_id)
    )
    return result.scalar_one_or_none()


def player_bans(match: Match, player_id: int) -> list[MatchBan]:
    return [ban for ban in match.bans if ban.player_id == player_id]


async def submit_ban(session: AsyncSession, match: Match, player_id: int, character_id: int) -> MatchBan:
    if match.status != STATUS_BAN_PHASE:
        raise ValueError("bans can only be submitted during the ban phase")
    if player_id not in (match.player1_id, match.player2_id):
        raise ValueError("only match participants can ban characters")
    if len(player_bans(match, player_id)) >= BAN_COUNT_PER_PLAYER:
        raise ValueError(f"each player may only ban {BAN_COUNT_PER_PLAYER} characters")
    if any(ban.character_id == character_id for ban in match.bans):
        raise ValueError("that character is already banned")

    ban = MatchBan(match_id=match.id, player_id=player_id, character_id=character_id)
    session.add(ban)
    match.bans.append(ban)
    await session.commit()
    return ban


def bans_complete(match: Match) -> bool:
    return (
        len(player_bans(match, match.player1_id)) >= BAN_COUNT_PER_PLAYER
        and len(player_bans(match, match.player2_id)) >= BAN_COUNT_PER_PLAYER
    )


async def assign_random_characters(
    session: AsyncSession, match: Match, *, prep_hours: int = PREP_MAX_HOURS
) -> tuple[MatchPick, MatchPick]:
    if match.status != STATUS_BAN_PHASE:
        raise ValueError("characters can only be assigned right after the ban phase")
    if not bans_complete(match):
        raise ValueError("both players must finish banning first")

    char_result = await session.execute(
        select(Character.id).where(Character.universe_id == match.universe_id)
    )
    all_character_ids = [row[0] for row in char_result.all()]
    banned_ids = {ban.character_id for ban in match.bans}

    char_a, char_b = draft.assign_random_characters(all_character_ids, banned_ids)

    pick1 = MatchPick(match_id=match.id, player_id=match.player1_id, character_id=char_a, is_random=True)
    pick2 = MatchPick(match_id=match.id, player_id=match.player2_id, character_id=char_b, is_random=True)
    session.add_all([pick1, pick2])
    match.picks.append(pick1)
    match.picks.append(pick2)

    match.status = STATUS_PREP
    match.phase_deadline = dt.datetime.utcnow() + dt.timedelta(hours=prep_hours)
    match.reminder_sent = False

    await session.commit()
    return pick1, pick2


async def assign_judges(session: AsyncSession, match: Match, judge_player_ids: list[int]) -> list[MatchJudge]:
    if match.player1_id in judge_player_ids or match.player2_id in judge_player_ids:
        raise ValueError("a match participant cannot also judge their own match")

    existing_ids = {j.judge_player_id for j in match.judges}
    created = []
    for judge_id in judge_player_ids:
        if judge_id in existing_ids:
            continue
        judge = MatchJudge(match_id=match.id, judge_player_id=judge_id)
        session.add(judge)
        match.judges.append(judge)
        created.append(judge)

    await session.commit()
    return created


def next_status(current: str) -> str | None:
    if current not in FLOW_ORDER:
        return None
    idx = FLOW_ORDER.index(current)
    if idx + 1 >= len(FLOW_ORDER):
        return None
    return FLOW_ORDER[idx + 1]


async def advance_phase(session: AsyncSession, match: Match) -> Match:
    """Manually advances the match to the next phase and (re)starts its timer.

    Judging can only be entered once both players have picks and at least
    MIN_JUDGES_PER_MATCH judges are assigned.
    """
    if match.status == STATUS_BAN_PHASE:
        raise ValueError(
            "the ban phase advances automatically once both players finish banning "
            "(characters are assigned at that point) — it cannot be skipped manually"
        )

    upcoming = next_status(match.status)
    if upcoming is None:
        raise ValueError(f"match is already in a terminal state: {match.status}")

    if upcoming == STATUS_ROUND_1 and len(match.picks) < 2:
        raise ValueError("characters must be assigned before rounds can start")
    if upcoming == STATUS_JUDGING and len(match.judges) < MIN_JUDGES_PER_MATCH:
        raise ValueError(f"at least {MIN_JUDGES_PER_MATCH} judges must be assigned before judging")

    match.status = upcoming
    match.reminder_sent = False
    minutes = _TIMED_PHASE_MINUTES.get(upcoming)
    match.phase_deadline = (
        dt.datetime.utcnow() + dt.timedelta(minutes=minutes) if minutes is not None else None
    )

    await session.commit()
    return match


async def matches_due_for_reminder(session: AsyncSession) -> list[Match]:
    now = dt.datetime.utcnow()
    result = await session.execute(
        select(Match).where(
            Match.phase_deadline.is_not(None),
            Match.phase_deadline <= now,
            Match.reminder_sent.is_(False),
            Match.status.in_(list(_TIMED_PHASE_MINUTES.keys())),
        )
    )
    return list(result.scalars().all())


async def mark_reminder_sent(session: AsyncSession, match: Match) -> None:
    match.reminder_sent = True
    await session.commit()


async def submit_score(
    session: AsyncSession,
    match: Match,
    *,
    judge_player_id: int,
    target_player_id: int,
    scores: dict[str, int],
) -> MatchScore:
    if match.status != STATUS_JUDGING:
        raise ValueError("scores can only be submitted during judging")
    if judge_player_id not in {j.judge_player_id for j in match.judges}:
        raise ValueError("this player is not an assigned judge for this match")
    if target_player_id not in (match.player1_id, match.player2_id):
        raise ValueError("target_player_id must be one of the match's players")

    total = scoring.total_score(scores)

    existing = next(
        (
            s
            for s in match.scores
            if s.judge_player_id == judge_player_id and s.target_player_id == target_player_id
        ),
        None,
    )
    if existing:
        existing.evidence_score = scores["evidence"]
        existing.argumentation_score = scores["argumentation"]
        existing.scaling_score = scores["scaling"]
        existing.defense_score = scores["defense"]
        existing.attack_score = scores["attack"]
        existing.math_score = scores["math"]
        existing.structure_score = scores["structure"]
        existing.total_score = total
        await session.commit()
        return existing

    record = MatchScore(
        match_id=match.id,
        judge_player_id=judge_player_id,
        target_player_id=target_player_id,
        evidence_score=scores["evidence"],
        argumentation_score=scores["argumentation"],
        scaling_score=scores["scaling"],
        defense_score=scores["defense"],
        attack_score=scores["attack"],
        math_score=scores["math"],
        structure_score=scores["structure"],
        total_score=total,
    )
    session.add(record)
    match.scores.append(record)
    await session.commit()
    return record


def scoring_progress(match: Match) -> dict[int, set[int]]:
    """Maps judge_player_id -> set of target_player_ids they've already scored."""
    progress: dict[int, set[int]] = {}
    for score in match.scores:
        progress.setdefault(score.judge_player_id, set()).add(score.target_player_id)
    return progress


def scores_complete(match: Match) -> bool:
    judge_ids = {j.judge_player_id for j in match.judges}
    if len(judge_ids) < MIN_JUDGES_PER_MATCH:
        return False
    progress = scoring_progress(match)
    targets = {match.player1_id, match.player2_id}
    return all(progress.get(jid, set()) == targets for jid in judge_ids)


async def finalize_match(session: AsyncSession, match: Match) -> scoring.MatchOutcome:
    if match.status != STATUS_JUDGING:
        raise ValueError("only matches in judging can be finalized")
    if not scores_complete(match):
        raise ValueError("not all assigned judges have scored both players yet")

    p1_totals = [s.total_score for s in match.scores if s.target_player_id == match.player1_id]
    p2_totals = [s.total_score for s in match.scores if s.target_player_id == match.player2_id]
    p1_votes = sum(1 for v in match.votes if v.voted_for_player_id == match.player1_id)
    p2_votes = sum(1 for v in match.votes if v.voted_for_player_id == match.player2_id)

    outcome = scoring.determine_outcome(p1_totals, p2_totals, p1_votes, p2_votes)

    player1 = await session.get(PlayerProfile, match.player1_id)
    player2 = await session.get(PlayerProfile, match.player2_id)
    if player1 is None or player2 is None:
        raise ValueError("match players not found")

    if outcome.winner is None:
        score_a = 0.5
        match.is_draw = True
        match.winner_id = None
        player1.draws += 1
        player2.draws += 1
    elif outcome.winner == 1:
        score_a = 1.0
        match.winner_id = player1.id
        player1.wins += 1
        player2.losses += 1
    else:
        score_a = 0.0
        match.winner_id = player2.id
        player1.losses += 1
        player2.wins += 1

    elo1_before, elo2_before = player1.elo, player2.elo
    elo1_after, elo2_after = update_ratings(elo1_before, elo2_before, score_a)
    player1.elo, player2.elo = elo1_after, elo2_after

    session.add_all(
        [
            EloHistory(
                player_id=player1.id,
                match_id=match.id,
                elo_before=elo1_before,
                elo_after=elo1_after,
                reason="match",
            ),
            EloHistory(
                player_id=player2.id,
                match_id=match.id,
                elo_before=elo2_before,
                elo_after=elo2_after,
                reason="match",
            ),
        ]
    )

    for judge_id in {j.judge_player_id for j in match.judges}:
        judge_profile = await session.get(PlayerProfile, judge_id)
        if judge_profile:
            judge_profile.judge_matches_count += 1

    match.status = STATUS_COMPLETED
    match.completed_at = dt.datetime.utcnow()
    match.phase_deadline = None

    await session.commit()
    return outcome
