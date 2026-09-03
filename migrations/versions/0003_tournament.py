"""power battle tournament module

Revision ID: 0003_tournament
Revises: 0002_post_tracking
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_tournament"
down_revision = "0002_post_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tournament_chats",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_chat_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("registered_by_tg_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tournament_admins",
        sa.Column("tg_user_id", sa.BigInteger, primary_key=True),
        sa.Column("added_by_tg_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tournament_seasons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "player_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("elo", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_judge", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("judge_matches_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "universes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("created_by_tg_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("universe_id", sa.Integer, sa.ForeignKey("universes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("universe_id", "name", name="uq_universe_character"),
    )

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("season_id", sa.Integer, sa.ForeignKey("tournament_seasons.id"), nullable=True),
        sa.Column("universe_id", sa.Integer, sa.ForeignKey("universes.id"), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slots", sa.Integer, nullable=False, server_default="8"),
        sa.Column("status", sa.String(32), nullable=False, server_default="registration"),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("announce_message_id", sa.BigInteger, nullable=True),
        sa.Column("created_by_tg_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tournament_signups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tournament_id", sa.Integer, sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("player_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tournament_id", "player_id", name="uq_tournament_player"),
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tournament_id", sa.Integer, sa.ForeignKey("tournaments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("round_number", sa.Integer, nullable=True),
        sa.Column("universe_id", sa.Integer, sa.ForeignKey("universes.id"), nullable=False),
        sa.Column("player1_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("player2_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ban_phase"),
        sa.Column("current_round", sa.Integer, nullable=False, server_default="0"),
        sa.Column("phase_deadline", sa.DateTime, nullable=True),
        sa.Column("reminder_sent", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("winner_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=True),
        sa.Column("is_draw", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("created_by_tg_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_matches_pending_reminder", "matches", ["status", "phase_deadline", "reminder_sent"])

    op.create_table(
        "match_bans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("character_id", sa.Integer, sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("match_id", "character_id", name="uq_match_ban_character"),
    )

    op.create_table(
        "match_picks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("character_id", sa.Integer, sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("version_note", sa.String(255), nullable=True),
        sa.Column("is_random", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("match_id", "player_id", name="uq_match_pick_player"),
    )

    op.create_table(
        "match_judges",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("judge_player_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("match_id", "judge_player_id", name="uq_match_judge"),
    )

    op.create_table(
        "match_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("judge_player_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("target_player_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("evidence_score", sa.Integer, nullable=False),
        sa.Column("argumentation_score", sa.Integer, nullable=False),
        sa.Column("scaling_score", sa.Integer, nullable=False),
        sa.Column("defense_score", sa.Integer, nullable=False),
        sa.Column("attack_score", sa.Integer, nullable=False),
        sa.Column("math_score", sa.Integer, nullable=False),
        sa.Column("structure_score", sa.Integer, nullable=False),
        sa.Column("total_score", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("match_id", "judge_player_id", "target_player_id", name="uq_match_score"),
    )

    op.create_table(
        "match_votes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter_tg_id", sa.BigInteger, nullable=False),
        sa.Column("voted_for_player_id", sa.Integer, sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("match_id", "voter_tg_id", name="uq_match_vote_voter"),
    )

    op.create_table(
        "elo_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("player_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("elo_before", sa.Integer, nullable=False),
        sa.Column("elo_after", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("elo_history")
    op.drop_table("match_votes")
    op.drop_table("match_scores")
    op.drop_table("match_judges")
    op.drop_table("match_picks")
    op.drop_table("match_bans")
    op.drop_index("ix_matches_pending_reminder", table_name="matches")
    op.drop_table("matches")
    op.drop_table("tournament_signups")
    op.drop_table("tournaments")
    op.drop_table("characters")
    op.drop_table("universes")
    op.drop_table("player_profiles")
    op.drop_table("tournament_seasons")
    op.drop_table("tournament_admins")
    op.drop_table("tournament_chats")
