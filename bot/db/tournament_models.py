from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class TournamentChat(Base):
    """The chat where tournament announcements, polls and votes are posted."""

    __tablename__ = "tournament_chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registered_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)


class TournamentAdmin(Base):
    __tablename__ = "tournament_admins"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    added_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)


class Season(Base):
    __tablename__ = "tournament_seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    ended_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    elo: Mapped[int] = mapped_column(Integer, default=1000)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    is_judge: Mapped[bool] = mapped_column(Boolean, default=False)
    judge_matches_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    @property
    def matches_played(self) -> int:
        return self.wins + self.losses + self.draws


class EloHistory(Base):
    __tablename__ = "elo_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id", ondelete="CASCADE"))
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    elo_before: Mapped[int] = mapped_column(Integer)
    elo_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)


class Universe(Base):
    __tablename__ = "universes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    characters: Mapped[list["Character"]] = relationship(
        back_populates="universe", cascade="all, delete-orphan"
    )


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("universe_id", "name", name="uq_universe_character"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    universe: Mapped["Universe"] = relationship(back_populates="characters")


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("tournament_seasons.id"), nullable=True)
    universe_id: Mapped[int | None] = mapped_column(ForeignKey("universes.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    slots: Mapped[int] = mapped_column(Integer, default=8)
    status: Mapped[str] = mapped_column(String(32), default="registration")
    chat_id: Mapped[int] = mapped_column(BigInteger)
    announce_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    signups: Mapped[list["TournamentSignup"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )


class TournamentSignup(Base):
    __tablename__ = "tournament_signups"
    __table_args__ = (UniqueConstraint("tournament_id", "player_id", name="uq_tournament_player"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id", ondelete="CASCADE"))
    joined_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    tournament: Mapped["Tournament"] = relationship(back_populates="signups")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int | None] = mapped_column(
        ForeignKey("tournaments.id", ondelete="SET NULL"), nullable=True
    )
    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universes.id"))
    player1_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    player2_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    status: Mapped[str] = mapped_column(String(32), default="ban_phase")
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    phase_deadline: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("player_profiles.id"), nullable=True)
    is_draw: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    completed_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    bans: Mapped[list["MatchBan"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    picks: Mapped[list["MatchPick"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    judges: Mapped[list["MatchJudge"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    scores: Mapped[list["MatchScore"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    votes: Mapped[list["MatchVote"]] = relationship(back_populates="match", cascade="all, delete-orphan")


class MatchBan(Base):
    __tablename__ = "match_bans"
    __table_args__ = (UniqueConstraint("match_id", "character_id", name="uq_match_ban_character"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    match: Mapped["Match"] = relationship(back_populates="bans")


class MatchPick(Base):
    __tablename__ = "match_picks"
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_match_pick_player"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    version_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_random: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    match: Mapped["Match"] = relationship(back_populates="picks")


class MatchJudge(Base):
    __tablename__ = "match_judges"
    __table_args__ = (UniqueConstraint("match_id", "judge_player_id", name="uq_match_judge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    judge_player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    assigned_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    match: Mapped["Match"] = relationship(back_populates="judges")


class MatchScore(Base):
    __tablename__ = "match_scores"
    __table_args__ = (
        UniqueConstraint("match_id", "judge_player_id", "target_player_id", name="uq_match_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    judge_player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    target_player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    evidence_score: Mapped[int] = mapped_column(Integer)
    argumentation_score: Mapped[int] = mapped_column(Integer)
    scaling_score: Mapped[int] = mapped_column(Integer)
    defense_score: Mapped[int] = mapped_column(Integer)
    attack_score: Mapped[int] = mapped_column(Integer)
    math_score: Mapped[int] = mapped_column(Integer)
    structure_score: Mapped[int] = mapped_column(Integer)
    total_score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    match: Mapped["Match"] = relationship(back_populates="scores")


class MatchVote(Base):
    __tablename__ = "match_votes"
    __table_args__ = (UniqueConstraint("match_id", "voter_tg_id", name="uq_match_vote_voter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    voter_tg_id: Mapped[int] = mapped_column(BigInteger)
    voted_for_player_id: Mapped[int] = mapped_column(ForeignKey("player_profiles.id"))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    match: Mapped["Match"] = relationship(back_populates="votes")
