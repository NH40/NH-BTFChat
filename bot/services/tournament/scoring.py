from __future__ import annotations

from dataclasses import dataclass

from bot.constant import JUDGE_WEIGHT, SCORE_CATEGORIES, VIEWER_WEIGHT


@dataclass(frozen=True)
class MatchOutcome:
    player1_judge_avg: float
    player2_judge_avg: float
    player1_viewer_votes: int
    player2_viewer_votes: int
    player1_weighted: float
    player2_weighted: float
    winner: int | None  # 1, 2, or None for a draw
    margin: float


def validate_category_scores(scores: dict[str, int]) -> None:
    for key, max_value in SCORE_CATEGORIES.items():
        if key not in scores:
            raise ValueError(f"missing score category: {key}")
        value = scores[key]
        if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= max_value):
            raise ValueError(f"{key} must be an integer between 0 and {max_value}")


def total_score(scores: dict[str, int]) -> int:
    validate_category_scores(scores)
    return sum(scores.values())


def average_totals(totals: list[int]) -> float:
    if not totals:
        return 0.0
    return sum(totals) / len(totals)


def determine_outcome(
    player1_judge_totals: list[int],
    player2_judge_totals: list[int],
    player1_votes: int,
    player2_votes: int,
    *,
    judge_weight: float = JUDGE_WEIGHT,
    viewer_weight: float = VIEWER_WEIGHT,
) -> MatchOutcome:
    """Blends the judges' average score with the chat's viewer vote split.

    Judges decide `judge_weight` of the outcome, viewers decide `viewer_weight`.
    Each side's "share" is its score/votes as a fraction of the two players' combined
    total, so a blowout on points matters more than a narrow one.
    """
    p1_avg = average_totals(player1_judge_totals)
    p2_avg = average_totals(player2_judge_totals)

    judge_sum = p1_avg + p2_avg
    p1_judge_share = (p1_avg / judge_sum) if judge_sum else 0.5
    p2_judge_share = 1 - p1_judge_share

    total_votes = player1_votes + player2_votes
    p1_viewer_share = (player1_votes / total_votes) if total_votes else 0.5
    p2_viewer_share = 1 - p1_viewer_share

    p1_weighted = p1_judge_share * judge_weight + p1_viewer_share * viewer_weight
    p2_weighted = p2_judge_share * judge_weight + p2_viewer_share * viewer_weight

    if abs(p1_weighted - p2_weighted) < 1e-9:
        winner = None
    else:
        winner = 1 if p1_weighted > p2_weighted else 2

    return MatchOutcome(
        player1_judge_avg=p1_avg,
        player2_judge_avg=p2_avg,
        player1_viewer_votes=player1_votes,
        player2_viewer_votes=player2_votes,
        player1_weighted=p1_weighted,
        player2_weighted=p2_weighted,
        winner=winner,
        margin=abs(p1_weighted - p2_weighted),
    )
