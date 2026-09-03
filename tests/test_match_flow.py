import pytest
from sqlalchemy import select

from bot.constant import BAN_COUNT_PER_PLAYER, MIN_JUDGES_PER_MATCH
from bot.db import EloHistory
from bot.services.tournament import matches as match_service
from bot.services.tournament import players as player_service
from bot.services.tournament import universes as universe_service


async def _setup_universe_with_characters(session, count: int = 12):
    universe = await universe_service.create_universe(session, name="Solo Leveling", created_by_tg_id=1)
    characters = []
    for i in range(count):
        characters.append(
            await universe_service.add_character(session, universe_id=universe.id, name=f"Char {i}")
        )
    return universe, characters


async def test_full_match_lifecycle_produces_winner_and_elo_change(session):
    universe, characters = await _setup_universe_with_characters(session)

    p1 = await player_service.get_or_create_player(session, tg_user_id=101, display_name="Alice")
    p2 = await player_service.get_or_create_player(session, tg_user_id=102, display_name="Bob")
    j1 = await player_service.get_or_create_player(session, tg_user_id=201, display_name="Judge1")
    j2 = await player_service.get_or_create_player(session, tg_user_id=202, display_name="Judge2")
    j3 = await player_service.get_or_create_player(session, tg_user_id=203, display_name="Judge3")

    match = await match_service.create_match(
        session,
        universe_id=universe.id,
        player1_id=p1.id,
        player2_id=p2.id,
        chat_id=-100,
        created_by_tg_id=1,
    )
    assert match.status == match_service.STATUS_BAN_PHASE

    match = await match_service.get_match(session, match.id)
    for i in range(BAN_COUNT_PER_PLAYER):
        await match_service.submit_ban(session, match, p1.id, characters[i].id)
        await match_service.submit_ban(session, match, p2.id, characters[i + 3].id)

    match = await match_service.get_match(session, match.id)
    assert match_service.bans_complete(match)

    pick1, pick2 = await match_service.assign_random_characters(session, match, prep_hours=1)
    banned_ids = {characters[i].id for i in range(6)}
    assert pick1.character_id not in banned_ids
    assert pick2.character_id not in banned_ids
    assert pick1.character_id != pick2.character_id

    match = await match_service.get_match(session, match.id)
    assert match.status == match_service.STATUS_PREP
    assert match.phase_deadline is not None

    for expected in (
        match_service.STATUS_ROUND_1,
        match_service.STATUS_ROUND_2,
        match_service.STATUS_ROUND_3,
        match_service.STATUS_FINAL_STATEMENT,
    ):
        match = await match_service.advance_phase(session, match)
        assert match.status == expected

    # judging requires MIN_JUDGES_PER_MATCH judges assigned first
    with pytest.raises(ValueError):
        await match_service.advance_phase(session, match)

    await match_service.assign_judges(session, match, [j1.id, j2.id, j3.id])
    match = await match_service.get_match(session, match.id)
    match = await match_service.advance_phase(session, match)
    assert match.status == match_service.STATUS_JUDGING

    scores_for_p1 = {
        "evidence": 24,
        "argumentation": 19,
        "scaling": 14,
        "defense": 14,
        "attack": 14,
        "math": 5,
        "structure": 5,
    }
    scores_for_p2 = {
        "evidence": 15,
        "argumentation": 10,
        "scaling": 8,
        "defense": 8,
        "attack": 8,
        "math": 2,
        "structure": 3,
    }

    assert not match_service.scores_complete(match)

    for judge in (j1, j2, j3):
        await match_service.submit_score(
            session, match, judge_player_id=judge.id, target_player_id=p1.id, scores=scores_for_p1
        )
        await match_service.submit_score(
            session, match, judge_player_id=judge.id, target_player_id=p2.id, scores=scores_for_p2
        )

    match = await match_service.get_match(session, match.id)
    assert match_service.scores_complete(match)
    assert len(match.judges) == MIN_JUDGES_PER_MATCH

    outcome = await match_service.finalize_match(session, match)
    assert outcome.winner == 1

    match = await match_service.get_match(session, match.id)
    assert match.status == match_service.STATUS_COMPLETED
    assert match.winner_id == p1.id
    assert match.completed_at is not None

    refreshed_p1 = await player_service.get_player_by_tg_id(session, 101)
    refreshed_p2 = await player_service.get_player_by_tg_id(session, 102)
    assert refreshed_p1.wins == 1
    assert refreshed_p2.losses == 1
    assert refreshed_p1.elo > 1000
    assert refreshed_p2.elo < 1000

    history = (await session.execute(select(EloHistory).where(EloHistory.match_id == match.id))).scalars().all()
    assert len(history) == 2

    for judge in (j1, j2, j3):
        refreshed_judge = await player_service.get_player_by_tg_id(session, judge.tg_user_id)
        assert refreshed_judge.judge_matches_count == 1


async def test_ban_phase_rejects_more_than_allowed_bans(session):
    universe, characters = await _setup_universe_with_characters(session, count=8)
    p1 = await player_service.get_or_create_player(session, tg_user_id=1)
    p2 = await player_service.get_or_create_player(session, tg_user_id=2)
    match = await match_service.create_match(
        session, universe_id=universe.id, player1_id=p1.id, player2_id=p2.id, chat_id=-1, created_by_tg_id=1
    )
    match = await match_service.get_match(session, match.id)

    for i in range(BAN_COUNT_PER_PLAYER):
        await match_service.submit_ban(session, match, p1.id, characters[i].id)

    with pytest.raises(ValueError):
        await match_service.submit_ban(session, match, p1.id, characters[BAN_COUNT_PER_PLAYER].id)


async def test_cannot_assign_characters_before_bans_complete(session):
    universe, characters = await _setup_universe_with_characters(session, count=8)
    p1 = await player_service.get_or_create_player(session, tg_user_id=1)
    p2 = await player_service.get_or_create_player(session, tg_user_id=2)
    match = await match_service.create_match(
        session, universe_id=universe.id, player1_id=p1.id, player2_id=p2.id, chat_id=-1, created_by_tg_id=1
    )
    match = await match_service.get_match(session, match.id)

    with pytest.raises(ValueError):
        await match_service.assign_random_characters(session, match)


async def test_advance_phase_cannot_skip_the_ban_phase(session):
    universe, characters = await _setup_universe_with_characters(session, count=8)
    p1 = await player_service.get_or_create_player(session, tg_user_id=1)
    p2 = await player_service.get_or_create_player(session, tg_user_id=2)
    match = await match_service.create_match(
        session, universe_id=universe.id, player1_id=p1.id, player2_id=p2.id, chat_id=-1, created_by_tg_id=1
    )
    match = await match_service.get_match(session, match.id)

    # Even with bans incomplete, advance_phase must never let a match skip
    # straight from ban_phase to prep without characters being assigned.
    with pytest.raises(ValueError):
        await match_service.advance_phase(session, match)


async def test_judge_cannot_be_a_match_participant(session):
    universe, _ = await _setup_universe_with_characters(session, count=4)
    p1 = await player_service.get_or_create_player(session, tg_user_id=1)
    p2 = await player_service.get_or_create_player(session, tg_user_id=2)
    match = await match_service.create_match(
        session, universe_id=universe.id, player1_id=p1.id, player2_id=p2.id, chat_id=-1, created_by_tg_id=1
    )
    match = await match_service.get_match(session, match.id)

    with pytest.raises(ValueError):
        await match_service.assign_judges(session, match, [p1.id])
