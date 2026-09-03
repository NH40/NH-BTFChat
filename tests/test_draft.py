import random

import pytest

from bot.services.tournament.draft import assign_random_characters, available_pool


def test_available_pool_excludes_banned():
    assert available_pool([1, 2, 3, 4], {2, 4}) == [1, 3]


def test_assign_random_characters_never_returns_banned():
    rng = random.Random(42)
    all_ids = list(range(1, 11))
    banned = {1, 2, 3, 4, 5, 6, 7, 8}  # only 9, 10 survive
    a, b = assign_random_characters(all_ids, banned, rng=rng)
    assert {a, b} == {9, 10}


def test_assign_random_characters_returns_distinct_characters():
    rng = random.Random(7)
    all_ids = list(range(1, 6))
    a, b = assign_random_characters(all_ids, banned_ids=set(), rng=rng)
    assert a != b
    assert a in all_ids and b in all_ids


def test_assign_random_characters_raises_when_pool_too_small():
    with pytest.raises(ValueError):
        assign_random_characters([1, 2, 3], banned_ids={2, 3}, rng=random.Random(1))


def test_assign_random_characters_is_deterministic_with_seeded_rng():
    all_ids = list(range(1, 21))
    a1, b1 = assign_random_characters(all_ids, set(), rng=random.Random(99))
    a2, b2 = assign_random_characters(all_ids, set(), rng=random.Random(99))
    assert (a1, b1) == (a2, b2)
