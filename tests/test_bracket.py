import random

import pytest

from bot.services.tournament import matches as match_service
from bot.services.tournament import players as player_service
from bot.services.tournament import tournaments as tournament_service
from bot.services.tournament import universes as universe_service


async def _complete_match_with_winner(session, match, winner_player_id, loser_player_id):
    """Fast-forwards a match straight to a judged win, bypassing the phase-by-phase
    ceremony (already covered by test_match_flow.py) so bracket tests stay focused
    on pairing/advancement logic.
    """
    match.status = match_service.STATUS_JUDGING
    await session.commit()

    j1 = await player_service.get_or_create_player(session, tg_user_id=9001)
    j2 = await player_service.get_or_create_player(session, tg_user_id=9002)
    j3 = await player_service.get_or_create_player(session, tg_user_id=9003)
    await match_service.assign_judges(session, match, [j1.id, j2.id, j3.id])
    match = await match_service.get_match(session, match.id)

    winner_scores = {
        "evidence": 25,
        "argumentation": 20,
        "scaling": 15,
        "defense": 15,
        "attack": 15,
        "math": 5,
        "structure": 5,
    }
    loser_scores = {k: 0 for k in winner_scores}

    for judge in (j1, j2, j3):
        await match_service.submit_score(
            session, match, judge_player_id=judge.id, target_player_id=winner_player_id, scores=winner_scores
        )
        await match_service.submit_score(
            session, match, judge_player_id=judge.id, target_player_id=loser_player_id, scores=loser_scores
        )

    match = await match_service.get_match(session, match.id)
    await match_service.finalize_match(session, match)
    return await match_service.get_match(session, match.id)


async def test_bracket_requires_power_of_two_slots(session):
    with pytest.raises(ValueError):
        await tournament_service.create_tournament(
            session, name="Bad", chat_id=-1, created_by_tg_id=1, slots=5
        )


async def test_signup_flow_fills_and_locks_bracket(session):
    tournament = await tournament_service.create_tournament(
        session, name="Season 1 Cup", chat_id=-1, created_by_tg_id=1, slots=4
    )
    players = [
        await player_service.get_or_create_player(session, tg_user_id=i) for i in range(1, 5)
    ]
    for p in players:
        await tournament_service.join_tournament(session, tournament, p.id)

    tournament = await tournament_service.get_tournament(session, tournament.id)
    assert tournament_service.is_full(tournament)

    with pytest.raises(ValueError):
        extra = await player_service.get_or_create_player(session, tg_user_id=999)
        await tournament_service.join_tournament(session, tournament, extra.id)


async def test_duplicate_signup_rejected(session):
    tournament = await tournament_service.create_tournament(
        session, name="Cup", chat_id=-1, created_by_tg_id=1, slots=4
    )
    p1 = await player_service.get_or_create_player(session, tg_user_id=1)
    await tournament_service.join_tournament(session, tournament, p1.id)
    tournament = await tournament_service.get_tournament(session, tournament.id)

    with pytest.raises(ValueError):
        await tournament_service.join_tournament(session, tournament, p1.id)


async def test_start_bracket_requires_a_universe(session):
    tournament = await tournament_service.create_tournament(
        session, name="No Universe Cup", chat_id=-1, created_by_tg_id=1, slots=4
    )
    players = [await player_service.get_or_create_player(session, tg_user_id=i) for i in range(1, 5)]
    for p in players:
        await tournament_service.join_tournament(session, tournament, p.id)

    tournament = await tournament_service.get_tournament(session, tournament.id)
    with pytest.raises(ValueError):
        await tournament_service.start_bracket(session, tournament)


async def test_four_player_bracket_runs_to_a_champion(session):
    universe = await universe_service.create_universe(session, name="U", created_by_tg_id=1)
    tournament = await tournament_service.create_tournament(
        session,
        name="4-man Cup",
        chat_id=-1,
        created_by_tg_id=1,
        universe_id=universe.id,
        slots=4,
    )
    players = [
        await player_service.get_or_create_player(session, tg_user_id=i) for i in range(1, 5)
    ]
    for p in players:
        await tournament_service.join_tournament(session, tournament, p.id)

    tournament = await tournament_service.get_tournament(session, tournament.id)
    round1 = await tournament_service.start_bracket(session, tournament, rng=random.Random(5))
    assert len(round1) == 2
    assert tournament.status == tournament_service.STATUS_IN_PROGRESS

    winners = []
    for match in round1:
        match = await match_service.get_match(session, match.id)
        winner_id, loser_id = match.player1_id, match.player2_id
        await _complete_match_with_winner(session, match, winner_id, loser_id)
        winners.append(winner_id)

    round2, champion = await tournament_service.advance_round(
        session, tournament, round_number=1, rng=random.Random(9)
    )
    assert champion is None
    assert len(round2) == 1

    final_match = await match_service.get_match(session, round2[0].id)
    final_winner = final_match.player1_id
    final_loser = final_match.player2_id
    assert final_winner in winners and final_loser in winners

    await _complete_match_with_winner(session, final_match, final_winner, final_loser)

    _, champion = await tournament_service.advance_round(session, tournament, round_number=2)
    assert champion == final_winner

    tournament = await tournament_service.get_tournament(session, tournament.id)
    assert tournament.status == tournament_service.STATUS_COMPLETED
