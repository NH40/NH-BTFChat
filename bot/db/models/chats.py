"""Чаты и каналы, где состоит бот, и общие настройки приложения."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base, utcnow

# Назначение чата (выбирает владелец в Mini App).
KIND_NONE = "none"
KIND_COMMUNITY = "community"  # чат с модерацией (и/или получатель пересылки)
KIND_ADMIN = "admin"  # чат админов — сюда идут напоминания по задачам
KIND_SERVICE = "service"  # служебный: проверка удаления постов пересылкой, сообщения тут копятся
KIND_CHANNEL = "channel"  # канал-источник пересылки
KINDS = (KIND_NONE, KIND_COMMUNITY, KIND_ADMIN, KIND_SERVICE, KIND_CHANNEL)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram chat id
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16))  # group / supergroup / channel
    kind: Mapped[str] = mapped_column(String(16), default=KIND_NONE)
    bot_status: Mapped[str] = mapped_column(String(16), default="member")  # member / administrator / left
    # Настройки модерации чата (антифлуд, ссылки, слова, предупреждения, приветствие) —
    # схема и значения по умолчанию в `services/moderation_settings.py`.
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AppSetting(Base):
    """Ключ → значение (JSON): служебный чат, чат админов, параметры проверки постов и т.д."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
