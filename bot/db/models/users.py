"""Пользователи Telegram и команда (роли для задач и Mini App)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base, utcnow

ROLE_OWNER = "owner"
ROLE_SENIOR = "senior"
ROLE_ADMIN = "admin"
ROLES = (ROLE_OWNER, ROLE_SENIOR, ROLE_ADMIN)
ROLE_LEVEL = {ROLE_ADMIN: 1, ROLE_SENIOR: 2, ROLE_OWNER: 3}


class TgUser(Base):
    """Любой пользователь, которого бот видел (нужен, чтобы находить людей по @username)."""

    __tablename__ = "tg_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def display_name(self) -> str:
        name = " ".join(x for x in (self.first_name, self.last_name) if x)
        return name or (f"@{self.username}" if self.username else str(self.id))


class Staff(Base):
    """Член команды: владелец / старший / админ. Владельцы из OWNER_IDS — всегда владельцы."""

    __tablename__ = "staff"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default=ROLE_ADMIN)
    title: Mapped[str | None] = mapped_column(String(128))  # должность / зона ответственности
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
