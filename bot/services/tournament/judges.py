from __future__ import annotations

import random


def select_random_judges(
    eligible_judge_ids: list[int],
    excluded_ids: set[int],
    count: int,
    *,
    rng: random.Random | None = None,
) -> list[int]:
    """Randomly picks `count` distinct judges, excluding the match's own players."""
    pool = [jid for jid in eligible_judge_ids if jid not in excluded_ids]
    if len(pool) < count:
        raise ValueError(f"not enough eligible judges: need {count}, have {len(pool)}")

    rng = rng or random.Random()
    return rng.sample(pool, count)
