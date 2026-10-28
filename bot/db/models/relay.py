"""Пересылка постов каналов в чаты: связки, отслеживаемые посты и их пересылки."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base, utcnow


class RelayRoute(Base):
    """Канал → чат. Любые пары: один канал в несколько чатов, несколько каналов в один чат."""

    __tablename__ = "relay_routes"
    __table_args__ = (UniqueConstraint("channel_id", "target_chat_id", name="uq_relay_route"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    target_chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RelayPost(Base):
    """Пост канала (одно сообщение или альбом). `version` растёт при каждой правке в канале."""

    __tablename__ = "relay_posts"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_relay_post"),
        Index("ix_relay_posts_check", "deleted", "last_checked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"))
    message_id: Mapped[int] = mapped_column(BigInteger)  # первое сообщение (для альбома — первое из группы)
    message_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))  # все сообщения поста (альбом)
    media_group_id: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RelayCopy(Base):
    """Пересылка поста в конкретный чат (id сообщений в чате — чтобы удалить при правке/удалении)."""

    __tablename__ = "relay_copies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("relay_posts.id", ondelete="CASCADE"), index=True)
    target_chat_id: Mapped[int] = mapped_column(BigInteger)
    message_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
