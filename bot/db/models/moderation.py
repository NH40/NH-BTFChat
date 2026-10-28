"""Модерация: предупреждения и журнал действий."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base, utcnow

ACT_BAN = "ban"
ACT_UNBAN = "unban"
ACT_MUTE = "mute"
ACT_UNMUTE = "unmute"
ACT_KICK = "kick"
ACT_WARN = "warn"
ACT_UNWARN = "unwarn"
ACT_DELETE = "delete"  # антиспам удалил сообщение


class ChatWarning(Base):
    __tablename__ = "chat_warnings"
    __table_args__ = (Index("ix_warnings_chat_user", "chat_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    issued_by: Mapped[int | None] = mapped_column(BigInteger)  # None — автоматически
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModAction(Base):
    __tablename__ = "mod_actions"
    __table_args__ = (Index("ix_mod_actions_chat_created", "chat_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"))
    target_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger)  # None — антиспам / автонаказание
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text)
    until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
