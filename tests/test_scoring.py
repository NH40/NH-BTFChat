import pytest

from bot.services.tournament.scoring import determine_outcome, total_score, validate_category_scores

FULL_MARKS = {
    "evidence": 25,
    "argumentation": 20,
    "scaling": 15,
    "defense": 15,
    "attack": 15,
    "math": 5,
    "structure": 5,
}


def test_total_score_sums_to_100_for_full_marks():
    assert total_score(FULL_MARKS) == 100


def test_validate_category_scores_rejects_missing_key():
    scores = dict(FULL_MARKS)
    del scores["math"]
    with pytest.raises(ValueError):
        validate_category_scores(scores)


def test_validate_category_scores_rejects_out_of_range():
    scores = dict(FULL_MARKS)
    scores["math"] = 6
    with pytest.raises(ValueError):
        validate_category_scores(scores)


def test_validate_category_scores_rejects_negative():
    scores = dict(FULL_MARKS)
    scores["structure"] = -1
    with pytest.raises(ValueError):
        validate_category_scores(scores)


def test_validate_category_scores_rejects_bool_as_int():
    scores = dict(FULL_MARKS)
    scores["math"] = True
    with pytest.raises(ValueError):
        validate_category_scores(scores)


def test_determine_outcome_pure_judge_win_no_votes():
    outcome = determine_outcome([90, 88], [70, 72], 0, 0)
    assert outcome.winner == 1
    assert outcome.player1_judge_avg == 89
    assert outcome.player2_judge_avg == 71


def test_determine_outcome_judges_favour_p2_but_viewers_favour_p1_judges_still_dominate():
    # judges 70%: p2 wins on points, viewers 30% all for p1 -> judge weight should still carry it
    outcome = determine_outcome([60, 60], [90, 90], player1_votes=1000, player2_votes=0)
    # p1 judge share = 60/150=0.4, viewer share=1.0 -> p1 weighted = 0.4*0.7+1.0*0.3=0.58
    # p2 judge share = 0.6, viewer share=0 -> p2 weighted = 0.6*0.7+0=0.42
    assert outcome.winner == 1
    assert outcome.player1_weighted == pytest.approx(0.58)
    assert outcome.player2_weighted == pytest.approx(0.42)


def test_determine_outcome_tie_is_a_draw():
    outcome = determine_outcome([80], [80], 5, 5)
    assert outcome.winner is None
    assert outcome.margin == pytest.approx(0.0)


def test_determine_outcome_handles_no_judge_scores_yet():
    outcome = determine_outcome([], [], 3, 1)
    # falls back to 50/50 judge share, viewers decide
    assert outcome.winner == 1
