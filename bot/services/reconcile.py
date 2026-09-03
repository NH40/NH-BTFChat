from __future__ import annotations

import asyncio
import datetime as dt
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import RECONCILE_BATCH_SIZE, RECONCILE_INTERVAL_SECONDS, RECONCILE_WINDOW
from bot.db import SourcePost, async_session_maker
from bot.services import posts as post_service

logger = logging.getLogger(__name__)

_NOT_FOUND_MARKERS = (
    "message to copy not found",
    "message to forward not found",
    "message identifier is not specified",
    "message id is invalid",
    "message_id_invalid",
)


async def run_reconciler(bot: Bot) -> None:
    while True:
        try:
            await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)
            await _reconcile_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reconciliation pass failed")


async def _reconcile_once(bot: Bot) -> None:
    async with async_session_maker() as session:
        since = dt.datetime.utcnow() - RECONCILE_WINDOW
        posts = await post_service.posts_due_for_check(session, since=since, limit=RECONCILE_BATCH_SIZE)
        for post in posts:
            await _check_post(session, bot, post)


async def _check_post(session: AsyncSession, bot: Bot, post: SourcePost) -> None:
    channel = post.channel
    owner = channel.owner if channel else None
    if channel is None or owner is None:
        await post_service.mark_checked(session, post.id)
        return

    exists = await _probe_message_exists(bot, owner.tg_user_id, channel.tg_chat_id, post.source_message_id)

    if exists is None or exists:
        await post_service.mark_checked(session, post.id)
        return

    for copy in post.copies:
        try:
            await bot.delete_message(chat_id=copy.target_chat_tg_id, message_id=copy.target_message_id)
        except Exception:
            logger.debug(
                "Could not delete stale copy %s in %s", copy.target_message_id, copy.target_chat_tg_id
            )

    await post_service.mark_deleted(session, post.id)


async def _probe_message_exists(
    bot: Bot, owner_tg_id: int, source_chat_id: int, message_id: int
) -> bool | None:
    """Best-effort existence check. Returns True/False, or None if inconclusive."""
    probe = None
    try:
        probe = await bot.copy_message(
            chat_id=owner_tg_id,
            from_chat_id=source_chat_id,
            message_id=message_id,
            disable_notification=True,
        )
    except TelegramForbiddenError:
        return None
    except TelegramBadRequest as exc:
        text = str(exc).lower()
        if any(marker in text for marker in _NOT_FOUND_MARKERS):
            return False
        return None
    except Exception:
        return None
    finally:
        if probe is not None:
            try:
                await bot.delete_message(chat_id=owner_tg_id, message_id=probe.message_id)
            except Exception:
                pass
    return True
