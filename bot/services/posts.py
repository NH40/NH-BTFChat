from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db import Channel, PostCopy, SourcePost


async def create_source_post(
    session: AsyncSession,
    *,
    channel_id: int,
    source_message_id: int,
    media_group_id: str | None = None,
) -> SourcePost:
    existing = await session.execute(
        select(SourcePost).where(
            SourcePost.channel_id == channel_id, SourcePost.source_message_id == source_message_id
        )
    )
    post = existing.scalar_one_or_none()
    if post:
        return post

    post = SourcePost(
        channel_id=channel_id, source_message_id=source_message_id, media_group_id=media_group_id
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


async def add_copy(
    session: AsyncSession,
    source_post_id: int,
    target_chat_tg_id: int,
    target_message_id: int,
    *,
    is_signature: bool = False,
) -> None:
    session.add(
        PostCopy(
            source_post_id=source_post_id,
            target_chat_tg_id=target_chat_tg_id,
            target_message_id=target_message_id,
            is_signature=is_signature,
        )
    )
    await session.commit()


async def get_source_post(
    session: AsyncSession, *, channel_id: int, source_message_id: int
) -> SourcePost | None:
    result = await session.execute(
        select(SourcePost)
        .options(selectinload(SourcePost.copies))
        .where(SourcePost.channel_id == channel_id, SourcePost.source_message_id == source_message_id)
    )
    return result.scalar_one_or_none()


async def remove_copy(session: AsyncSession, copy_id: int) -> None:
    copy = await session.get(PostCopy, copy_id)
    if copy:
        await session.delete(copy)
        await session.commit()


async def posts_due_for_check(
    session: AsyncSession, *, since: dt.datetime, limit: int
) -> list[SourcePost]:
    result = await session.execute(
        select(SourcePost)
        .options(
            selectinload(SourcePost.copies),
            selectinload(SourcePost.channel).selectinload(Channel.owner),
        )
        .where(SourcePost.is_deleted.is_(False), SourcePost.created_at >= since)
        .order_by(SourcePost.last_checked_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_checked(session: AsyncSession, source_post_id: int) -> None:
    post = await session.get(SourcePost, source_post_id)
    if post:
        post.last_checked_at = dt.datetime.utcnow()
        await session.commit()


async def mark_deleted(session: AsyncSession, source_post_id: int) -> None:
    post = await session.get(SourcePost, source_post_id)
    if post:
        post.is_deleted = True
        post.last_checked_at = dt.datetime.utcnow()
        await session.commit()
