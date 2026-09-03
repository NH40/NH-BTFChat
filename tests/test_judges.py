import random

import pytest

from bot.services.tournament.judges import select_random_judges


def test_select_random_judges_excludes_players():
    rng = random.Random(3)
    eligible = [1, 2, 3, 4, 5]
    chosen = select_random_judges(eligible, excluded_ids={1, 2}, count=3, rng=rng)
    assert len(chosen) == 3
    assert set(chosen).isdisjoint({1, 2})
    assert set(chosen).issubset({3, 4, 5})


def test_select_random_judges_returns_distinct_judges():
    rng = random.Random(11)
    chosen = select_random_judges(list(range(1, 21)), excluded_ids=set(), count=3, rng=rng)
    assert len(set(chosen)) == 3


def test_select_random_judges_raises_when_not_enough_eligible():
    with pytest.raises(ValueError):
        select_random_judges([1, 2], excluded_ids=set(), count=3, rng=random.Random(1))


def test_select_random_judges_excluded_players_never_have_enough_pool():
    with pytest.raises(ValueError):
        select_random_judges([1, 2, 3], excluded_ids={1, 2, 3}, count=1, rng=random.Random(1))
