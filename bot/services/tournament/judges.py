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
        raise ValueError(f"Недостаточно доступных судей: нужно {count}, есть {len(pool)}.")

    rng = rng or random.Random()
    return rng.sample(pool, count)
