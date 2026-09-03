"""Tuning constants for the Power Battle tournament module.

Several values here (season reset pull, judge/viewer weight split) were given only
as rough examples by the organizers, not exact formulas — they are implemented as
named constants specifically so they can be tuned without touching logic code.
"""

# --- Elo rating ---
ELO_DEFAULT = 1000
ELO_K_FACTOR = 32

# --- Season reset ---
# On season reset every player's rating is pulled back toward ELO_DEFAULT by this
# fraction of the distance, e.g. 0.7 means 70% of the gap to the baseline is removed:
#   new = ELO_DEFAULT + (old - ELO_DEFAULT) * (1 - SEASON_RESET_PULL)
SEASON_RESET_PULL = 0.7

# --- Winner determination weighting (judges vs chat viewers) ---
JUDGE_WEIGHT = 0.7
VIEWER_WEIGHT = 0.3

# --- PB scoring rubric (must sum to 100) ---
SCORE_CATEGORIES: dict[str, int] = {
    "evidence": 25,
    "argumentation": 20,
    "scaling": 15,
    "defense": 15,
    "attack": 15,
    "math": 5,
    "structure": 5,
}
MAX_TOTAL_SCORE = sum(SCORE_CATEGORIES.values())

# --- Ban phase / judging ---
BAN_COUNT_PER_PLAYER = 3
MIN_JUDGES_PER_MATCH = 3

# --- Timing (PB regulation, minutes unless noted) ---
PREP_MAX_HOURS = 24
ROUND1_MINUTES_PER_PLAYER = 15
ROUND2_MINUTES_PER_PLAYER = 10
ROUND3_MINUTES_PER_PLAYER = 10
FINAL_STATEMENT_P1_MINUTES = 5
FINAL_STATEMENT_P2_MINUTES = 1
VERDICT_MINUTES = 15

# --- Tournament brackets ---
DEFAULT_BRACKET_SLOTS = 8
MIN_PLAYERS_TO_START = 8

# --- Background scheduler tick for match phase deadlines ---
TOURNAMENT_TICK_SECONDS = 60
