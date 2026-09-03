from __future__ import annotations

import random


def available_pool(all_character_ids: list[int], banned_ids: set[int]) -> list[int]:
    return [cid for cid in all_character_ids if cid not in banned_ids]


def assign_random_characters(
    all_character_ids: list[int], banned_ids: set[int], *, rng: random.Random | None = None
) -> tuple[int, int]:
    """Randomly assigns two distinct characters (one per player) from whatever
    survived the ban phase. Raises ValueError if fewer than two remain.
    """
    pool = available_pool(all_character_ids, banned_ids)
    if len(pool) < 2:
        raise ValueError("not enough characters left after bans to assign two players")

    rng = rng or random.Random()
    chosen = rng.sample(pool, 2)
    return chosen[0], chosen[1]
