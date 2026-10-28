"""Пересылка постов каналов в чаты.

- Новый пост — настоящая пересылка («Переслано из …») во все активные чаты связки. Альбом
  приходит отдельными сообщениями с общим media_group_id — собираем их ~2 с и пересылаем разом.
- Правка поста в канале (edited_channel_post) — пересылки этой версии удаляются, свежая версия
  пересылается заново (пересылка всегда несёт текущее содержимое).
- Удаление поста Telegram боту не сообщает — проверяем пересылкой в СЛУЖЕБНЫЙ чат (там сообщения
  просто копятся, ничего не удаляется). Не нашлось — удаляем пересылки во всех чатах.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db import Chat, RelayCopy, RelayPost, RelayRoute
from bot.redis import redis
from bot.services import app_settings
from bot.utils.time import now

log = logging.getLogger(__name__)

ALBUM_WAIT_SECONDS = 2.0
EDIT_WAIT_SECONDS = 2.0
_NOT_FOUND = ("message to forward not found", "message_id_invalid", "message to copy not found", "message not found")
_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _targets(session: AsyncSession, channel_id: int) -> list[int]:
    rows = await session.scalars(
        select(RelayRoute.target_chat_id).join(Chat, Chat.id == RelayRoute.target_chat_id)
        .where(RelayRoute.channel_id == channel_id, RelayRoute.active.is_(True), Chat.bot_status != "left")
    )
    return list(rows)


async def _forward(bot: Bot, target: int, channel_id: int, ids: list[int]) -> list[int]:
    """Переслать сообщения (альбом — одним вызовом, чтобы остался альбомом). → id в чате."""
    for attempt in range(3):
        try:
            if len(ids) == 1:
                msg = await bot.forward_message(target, channel_id, ids[0])
                return [msg.message_id]
            res = await bot.forward_messages(target, channel_id, ids)
            return [m.message_id for m in res]
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramAPIError:
            log.exception("relay forward failed: %s → %s %s", channel_id, target, ids)
            return []
    return []


async def _delete_copies(bot: Bot, copies: list[RelayCopy]) -> None:
    for c in copies:
        try:
            await bot.delete_messages(c.target_chat_id, list(c.message_ids))
        except TelegramAPIError:
            log.warning("relay: не удалось удалить %s в %s", c.message_ids, c.target_chat_id)


async def publish(bot: Bot, session_factory: async_sessionmaker[AsyncSession], channel_id: int, ids: list[int],
                  media_group_id: str | None) -> None:
    """Новый пост: запомнить и переслать во все чаты связки."""
    ids = sorted(set(ids))
    async with session_factory() as session:
        targets = await _targets(session, channel_id)
        if not targets:
            return
        exists = await session.scalar(select(RelayPost.id).where(RelayPost.channel_id == channel_id, RelayPost.message_id == ids[0]))
        if exists:
            return
        post = RelayPost(channel_id=channel_id, message_id=ids[0], message_ids=ids, media_group_id=media_group_id)
        session.add(post)
        await session.flush()
        for target in targets:
            sent = await _forward(bot, target, channel_id, ids)
            if sent:
                session.add(RelayCopy(post_id=post.id, target_chat_id=target, message_ids=sent, version=1))
        await session.commit()


async def on_channel_post(bot: Bot, session_factory, channel_id: int, message_id: int, media_group_id: str | None) -> None:
    if not media_group_id:
        await publish(bot, session_factory, channel_id, [message_id], None)
        return
    key = f"relay:mg:{channel_id}:{media_group_id}"
    await redis.rpush(key, message_id)
    await redis.expire(key, 120)
    if await redis.set(f"{key}:lock", "1", nx=True, ex=60):
        async def flush() -> None:
            await asyncio.sleep(ALBUM_WAIT_SECONDS)
            ids = [int(x) for x in await redis.lrange(key, 0, -1)]
            await redis.delete(key)
            if ids:
                await publish(bot, session_factory, channel_id, ids, media_group_id)

        _spawn(flush())


async def reforward(bot: Bot, session: AsyncSession, post: RelayPost) -> None:
    """Удалить пересылки поста и переслать текущую версию заново (НЕ коммитит)."""
    copies = list(await session.scalars(select(RelayCopy).where(RelayCopy.post_id == post.id)))
    await _delete_copies(bot, copies)
    for c in copies:
        await session.delete(c)
    post.version += 1
    post.last_checked_at = now()
    for target in await _targets(session, post.channel_id):
        sent = await _forward(bot, target, post.channel_id, list(post.message_ids))
        if sent:
            session.add(RelayCopy(post_id=post.id, target_chat_id=target, message_ids=sent, version=post.version))


async def on_edit(bot: Bot, session_factory, channel_id: int, message_id: int) -> None:
    """Правка в канале: через пару секунд (правки альбома приходят пачкой) — переотправка."""
    async with session_factory() as session:
        post = await session.scalar(select(RelayPost).where(
            RelayPost.channel_id == channel_id, RelayPost.message_ids.any(message_id), RelayPost.deleted.is_(False)))
        if post is None:
            return
        post_id = post.id
    if not await redis.set(f"relay:edit:{post_id}", "1", nx=True, ex=30):
        return

    async def flush() -> None:
        await asyncio.sleep(EDIT_WAIT_SECONDS)
        await redis.delete(f"relay:edit:{post_id}")
        async with session_factory() as session:
            fresh = await session.get(RelayPost, post_id)
            if fresh is not None and not fresh.deleted:
                await reforward(bot, session, fresh)
                await session.commit()

    _spawn(flush())


async def _exists(bot: Bot, service_chat: int, channel_id: int, message_id: int) -> bool | None:
    """Есть ли сообщение в канале: пересылка в служебный чат (там остаётся, не удаляем).
    None — проверить не удалось (нет прав, лимит и т.п.)."""
    try:
        await bot.forward_message(service_chat, channel_id, message_id, disable_notification=True)
        return True
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 1)
        return None
    except TelegramBadRequest as exc:
        if any(m in str(exc).lower() for m in _NOT_FOUND):
            return False
        return None
    except TelegramAPIError:
        return None


async def check_deleted(bot: Bot, session_factory) -> int:
    """Один проход проверки удалённых постов. → сколько постов удалено из чатов."""
    async with session_factory() as session:
        cfg = await app_settings.get(session, app_settings.KEY_RELAY_CHECK)
        service = (await app_settings.get(session, app_settings.KEY_SERVICE_CHAT)).get("chat_id")
        if not cfg.get("enabled") or not service:
            return 0
        t = now()
        posts = list(await session.scalars(
            select(RelayPost).where(
                RelayPost.deleted.is_(False),
                RelayPost.created_at >= t - timedelta(hours=int(cfg["window_hours"])),
                RelayPost.last_checked_at <= t - timedelta(minutes=int(cfg["interval_minutes"])),
            ).order_by(RelayPost.last_checked_at).limit(int(cfg["batch"]))
        ))
        removed = 0
        for post in posts:
            alive: list[int] = []
            unknown = False
            for mid in post.message_ids:
                res = await _exists(bot, int(service), post.channel_id, mid)
                await asyncio.sleep(0.4)
                if res is None:
                    unknown = True
                elif res:
                    alive.append(mid)
            post.last_checked_at = now()
            if unknown:
                continue
            if not alive:
                copies = list(await session.scalars(select(RelayCopy).where(RelayCopy.post_id == post.id)))
                await _delete_copies(bot, copies)
                post.deleted = True
                removed += 1
            elif len(alive) < len(post.message_ids):
                post.message_ids = alive  # из альбома удалили часть — пересылаем оставшееся
                await reforward(bot, session, post)
        await session.commit()
        return removed
