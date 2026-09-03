from __future__ import annotations

from bot.constant import ELO_DEFAULT, ELO_K_FACTOR, SEASON_RESET_PULL


def expected_score(rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def update_ratings(
    rating_a: int, rating_b: int, score_a: float, *, k: int = ELO_K_FACTOR
) -> tuple[int, int]:
    """Standard Elo update. score_a is 1.0 if A won, 0.0 if A lost, 0.5 for a draw."""
    if not 0.0 <= score_a <= 1.0:
        raise ValueError("score_a must be between 0 and 1")

    expected_a = expected_score(rating_a, rating_b)
    score_b = 1 - score_a
    expected_b = 1 - expected_a

    new_a = round(rating_a + k * (score_a - expected_a))
    new_b = round(rating_b + k * (score_b - expected_b))
    return new_a, new_b


def season_reset_rating(
    rating: int, *, baseline: int = ELO_DEFAULT, pull: float = SEASON_RESET_PULL
) -> int:
    """Pulls a rating back toward the baseline by `pull` fraction of the distance.

    E.g. pull=0.7 removes 70% of the gap between the rating and the baseline.
    """
    if not 0.0 <= pull <= 1.0:
        raise ValueError("pull must be between 0 and 1")
    return round(baseline + (rating - baseline) * (1 - pull))
