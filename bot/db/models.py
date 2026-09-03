from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class BotUser(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    channels: Mapped[list["Channel"]] = relationship(back_populates="owner")
    target_chats: Mapped[list["TargetChat"]] = relationship(back_populates="owner")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_is_admin: Mapped[bool] = mapped_column(default=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    owner: Mapped["BotUser"] = relationship(back_populates="channels")
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class TargetChat(Base):
    __tablename__ = "target_chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_type: Mapped[str] = mapped_column(String(32))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    owner: Mapped["BotUser"] = relationship(back_populates="target_chats")
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="target_chat", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("channel_id", "target_chat_id", name="uq_channel_target"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    target_chat_id: Mapped[int] = mapped_column(ForeignKey("target_chats.id"))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    channel: Mapped["Channel"] = relationship(back_populates="subscriptions")
    target_chat: Mapped["TargetChat"] = relationship(back_populates="subscriptions")


class SourcePost(Base):
    __tablename__ = "source_posts"
    __table_args__ = (UniqueConstraint("channel_id", "source_message_id", name="uq_channel_message"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    media_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    last_checked_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    channel: Mapped["Channel"] = relationship()
    copies: Mapped[list["PostCopy"]] = relationship(
        back_populates="source_post", cascade="all, delete-orphan"
    )


class PostCopy(Base):
    __tablename__ = "post_copies"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_post_id: Mapped[int] = mapped_column(
        ForeignKey("source_posts.id", ondelete="CASCADE"), index=True
    )
    target_chat_tg_id: Mapped[int] = mapped_column(BigInteger)
    target_message_id: Mapped[int] = mapped_column(BigInteger)
    is_signature: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    source_post: Mapped["SourcePost"] = relationship(back_populates="copies")


class PendingAction(Base):
    __tablename__ = "pending_actions"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
