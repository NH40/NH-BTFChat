from bot.services.tournament import chat as chat_service
from bot.services.tournament import players as player_service
from bot.services.tournament import seasons as season_service
from bot.services.tournament import universes as universe_service


async def test_chat_registration_bootstraps_admin(session):
    assert not await chat_service.has_any_admin(session)

    tchat = await chat_service.register_chat(
        session, tg_chat_id=-1001, title="BTF Team", registered_by_tg_id=555
    )
    await chat_service.add_admin(session, 555, added_by_tg_id=555)

    assert tchat.tg_chat_id == -1001
    assert await chat_service.is_admin(session, 555)
    assert not await chat_service.is_admin(session, 999)
    assert await chat_service.get_registered_chat_id(session) == -1001


async def test_admin_promotion_and_removal(session):
    await chat_service.add_admin(session, 1, added_by_tg_id=1)
    await chat_service.add_admin(session, 2, added_by_tg_id=1)
    assert await chat_service.is_admin(session, 2)

    await chat_service.remove_admin(session, 2)
    assert not await chat_service.is_admin(session, 2)


async def test_player_lazily_created_with_default_elo(session):
    player = await player_service.get_or_create_player(session, tg_user_id=777, display_name="Newbie")
    assert player.elo == 1000
    assert player.wins == 0 and player.losses == 0 and player.draws == 0

    same = await player_service.get_or_create_player(session, tg_user_id=777, display_name="Newbie2")
    assert same.id == player.id
    assert same.display_name == "Newbie2"


async def test_leaderboard_orders_by_elo_desc(session):
    low = await player_service.get_or_create_player(session, tg_user_id=1)
    high = await player_service.get_or_create_player(session, tg_user_id=2)
    mid = await player_service.get_or_create_player(session, tg_user_id=3)

    low.elo = 800
    high.elo = 1400
    mid.elo = 1000
    await session.commit()

    board = await player_service.leaderboard(session, limit=10)
    assert [p.tg_user_id for p in board] == [2, 3, 1]


async def test_judge_flag_toggle(session):
    player = await player_service.get_or_create_player(session, tg_user_id=42)
    assert player.is_judge is False

    await player_service.set_judge_flag(session, 42, True)
    judges = await player_service.list_judges(session)
    assert any(j.tg_user_id == 42 for j in judges)

    await player_service.set_judge_flag(session, 42, False)
    judges = await player_service.list_judges(session)
    assert not any(j.tg_user_id == 42 for j in judges)


async def test_universe_and_character_crud(session):
    universe = await universe_service.create_universe(session, name="Tower of God", created_by_tg_id=1)
    await universe_service.add_character(session, universe_id=universe.id, name="Baam")
    char2 = await universe_service.add_character(session, universe_id=universe.id, name="Rachel")

    chars = await universe_service.list_characters(session, universe.id)
    assert {c.name for c in chars} == {"Baam", "Rachel"}

    await universe_service.remove_character(session, char2.id)
    chars = await universe_service.list_characters(session, universe.id)
    assert {c.name for c in chars} == {"Baam"}

    found = await universe_service.get_universe_by_name(session, "tower of god")
    assert found is not None and found.id == universe.id


async def test_season_reset_compresses_ratings_and_logs_history(session):
    p1 = await player_service.get_or_create_player(session, tg_user_id=1)
    p2 = await player_service.get_or_create_player(session, tg_user_id=2)
    p1.elo = 1500
    p2.elo = 600
    await session.commit()

    season = await season_service.start_season(session, "Season 1")
    assert season.is_active is True

    affected = await season_service.reset_all_ratings(session)
    assert affected == 2

    refreshed_p1 = await player_service.get_player_by_tg_id(session, 1)
    refreshed_p2 = await player_service.get_player_by_tg_id(session, 2)
    assert refreshed_p1.elo == 1150  # 1000 + (1500-1000)*0.3
    assert refreshed_p2.elo == 880  # 1000 + (600-1000)*0.3

    season2 = await season_service.start_season(session, "Season 2")
    assert season2.is_active is True
    old_season = await season_service.get_active_season(session)
    assert old_season.id == season2.id
