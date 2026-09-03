from bot.services.tournament.elo import expected_score, season_reset_rating, update_ratings


def test_expected_score_equal_ratings_is_half():
    assert expected_score(1000, 1000) == 0.5


def test_expected_score_higher_rating_favoured():
    assert expected_score(1200, 1000) > 0.5
    assert expected_score(1000, 1200) < 0.5


def test_update_ratings_winner_gains_loser_loses():
    new_a, new_b = update_ratings(1000, 1000, score_a=1.0)
    assert new_a > 1000
    assert new_b < 1000
    # zero-sum for equal ratings
    assert (new_a - 1000) == -(new_b - 1000)


def test_update_ratings_draw_keeps_equal_ratings_unchanged():
    new_a, new_b = update_ratings(1000, 1000, score_a=0.5)
    assert new_a == 1000
    assert new_b == 1000


def test_update_ratings_underdog_win_gains_more_than_favourite_win():
    # underdog (b, rated lower) beats favourite (a, rated higher)
    underdog_gain_a, underdog_gain_b = update_ratings(1200, 800, score_a=0.0)
    fav_gain_a, fav_gain_b = update_ratings(1200, 800, score_a=1.0)

    underdog_gain = underdog_gain_b - 800
    favourite_gain = fav_gain_a - 1200
    assert underdog_gain > favourite_gain


def test_update_ratings_rejects_invalid_score():
    import pytest

    with pytest.raises(ValueError):
        update_ratings(1000, 1000, score_a=1.5)


def test_season_reset_pulls_toward_baseline():
    assert season_reset_rating(1000, baseline=1000, pull=0.7) == 1000
    # a rating far above baseline loses most (but not all) of its lead
    reset = season_reset_rating(1500, baseline=1000, pull=0.7)
    assert 1000 < reset < 1500
    assert reset == 1150  # 1000 + (1500-1000)*0.3


def test_season_reset_pulls_low_ratings_up_too():
    reset = season_reset_rating(600, baseline=1000, pull=0.7)
    assert 600 < reset < 1000
    assert reset == 880  # 1000 + (600-1000)*0.3


def test_season_reset_rejects_invalid_pull():
    import pytest

    with pytest.raises(ValueError):
        season_reset_rating(1000, pull=1.5)
