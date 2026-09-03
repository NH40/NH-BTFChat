import asyncio
import logging
from collections import defaultdict

from aiogram import Bot, Router
from aiogram.enums import ContentType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import ALBUM_DEBOUNCE_SECONDS, MAX_CAPTION_LENGTH, MAX_TEXT_LENGTH
from bot.db import Channel, async_session_maker
from bot.services import channels as channel_service
from bot.services import posts as post_service
from bot.services import subscriptions as sub_service
from bot.utils import append_signature, build_signature

router = Router(name="posts")
logger = logging.getLogger(__name__)

_CAPTIONABLE = {
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.DOCUMENT,
    ContentType.AUDIO,
    ContentType.ANIMATION,
    ContentType.VOICE,
}

_album_buffers: dict[tuple[int, str], list[Message]] = defaultdict(list)
_album_tasks: dict[tuple[int, str], asyncio.Task] = {}


def _supports_caption(content_type: str) -> bool:
    return content_type in _CAPTIONABLE


@router.channel_post()
async def on_channel_post(message: Message, session: AsyncSession, bot: Bot) -> None:
    db_channel = await channel_service.get_channel_by_tg_id(session, message.chat.id)
    if not db_channel or not db_channel.bot_is_admin:
        return

    if message.media_group_id:
        _buffer_album_part(message, db_channel.id, bot)
        return

    target_chat_ids = await sub_service.list_targets_for_channel(session, db_channel.id)
    if not target_chat_ids:
        return

    source_post = await post_service.create_source_post(
        session, channel_id=db_channel.id, source_message_id=message.message_id
    )
    signature = build_signature(db_channel)

    for tg_chat_id in target_chat_ids:
        try:
            copies = await _send_single_copy(bot, message, tg_chat_id, signature)
            for target_message_id, is_signature in copies:
                await post_service.add_copy(
                    session, source_post.id, tg_chat_id, target_message_id, is_signature=is_signature
                )
        except Exception:
            logger.exception("Failed to copy message %s to %s", message.message_id, tg_chat_id)


async def _send_single_copy(
    bot: Bot, message: Message, tg_chat_id: int, signature: str
) -> list[tuple[int, bool]]:
    if message.content_type == ContentType.TEXT:
        text = append_signature(message.html_text, signature, MAX_TEXT_LENGTH)
        result = await bot.send_message(chat_id=tg_chat_id, text=text, parse_mode=ParseMode.HTML)
        return [(result.message_id, False)]

    if _supports_caption(message.content_type):
        caption = append_signature(
            message.html_text if message.caption else None, signature, MAX_CAPTION_LENGTH
        )
        result = await bot.copy_message(
            chat_id=tg_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        return [(result.message_id, False)]

    result = await bot.copy_message(
        chat_id=tg_chat_id, from_chat_id=message.chat.id, message_id=message.message_id
    )
    copies = [(result.message_id, False)]
    try:
        footer = await bot.send_message(
            chat_id=tg_chat_id, text=signature.strip(), parse_mode=ParseMode.HTML, disable_notification=True
        )
        copies.append((footer.message_id, True))
    except Exception:
        logger.exception("Failed to send source signature to %s", tg_chat_id)
    return copies


def _buffer_album_part(message: Message, channel_id: int, bot: Bot) -> None:
    key = (message.chat.id, message.media_group_id)
    _album_buffers[key].append(message)

    existing = _album_tasks.get(key)
    if existing and not existing.done():
        existing.cancel()

    _album_tasks[key] = asyncio.create_task(_flush_album_later(key, channel_id, bot))


async def _flush_album_later(key: tuple[int, str], channel_id: int, bot: Bot) -> None:
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return

    messages = _album_buffers.pop(key, [])
    _album_tasks.pop(key, None)
    if not messages:
        return

    messages.sort(key=lambda m: m.message_id)
    source_chat_id, media_group_id = key

    async with async_session_maker() as session:
        channel = await session.get(Channel, channel_id)
        if channel is None:
            return

        target_chat_ids = await sub_service.list_targets_for_channel(session, channel_id)
        if not target_chat_ids:
            return

        source_posts = {}
        for item in messages:
            source_posts[item.message_id] = await post_service.create_source_post(
                session,
                channel_id=channel_id,
                source_message_id=item.message_id,
                media_group_id=media_group_id,
            )
        last_source_post = source_posts[max(source_posts)]
        signature = build_signature(channel)

        message_ids = [item.message_id for item in messages]
        for tg_chat_id in target_chat_ids:
            try:
                results = await bot.copy_messages(
                    chat_id=tg_chat_id, from_chat_id=source_chat_id, message_ids=message_ids
                )
            except Exception:
                logger.exception("Failed to copy album %s to %s", media_group_id, tg_chat_id)
                continue

            for src_message_id, result in zip(message_ids, results):
                await post_service.add_copy(session, source_posts[src_message_id].id, tg_chat_id, result.message_id)

            try:
                footer = await bot.send_message(
                    chat_id=tg_chat_id,
                    text=signature.strip(),
                    parse_mode=ParseMode.HTML,
                    disable_notification=True,
                )
                await post_service.add_copy(
                    session, last_source_post.id, tg_chat_id, footer.message_id, is_signature=True
                )
            except Exception:
                logger.exception("Failed to send album signature to %s", tg_chat_id)


@router.edited_channel_post()
async def on_edited_channel_post(message: Message, session: AsyncSession, bot: Bot) -> None:
    db_channel = await channel_service.get_channel_by_tg_id(session, message.chat.id)
    if not db_channel or not db_channel.bot_is_admin:
        return

    source_post = await post_service.get_source_post(
        session, channel_id=db_channel.id, source_message_id=message.message_id
    )
    if not source_post or source_post.is_deleted:
        return

    signature = build_signature(db_channel)
    for copy in list(source_post.copies):
        await _apply_edit(bot, session, message, copy, signature)


async def _apply_edit(bot: Bot, session: AsyncSession, message: Message, copy, signature: str) -> None:
    if copy.is_signature:
        return

    try:
        if message.content_type == ContentType.TEXT:
            text = append_signature(message.html_text, signature, MAX_TEXT_LENGTH)
            await bot.edit_message_text(
                chat_id=copy.target_chat_tg_id,
                message_id=copy.target_message_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            return

        media = _build_input_media(message, signature)
        if media is not None:
            await bot.edit_message_media(
                chat_id=copy.target_chat_tg_id, message_id=copy.target_message_id, media=media
            )
            return

        if _supports_caption(message.content_type):
            caption = append_signature(
                message.html_text if message.caption else None, signature, MAX_CAPTION_LENGTH
            )
            await bot.edit_message_caption(
                chat_id=copy.target_chat_tg_id,
                message_id=copy.target_message_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
    except TelegramBadRequest as exc:
        text = str(exc).lower()
        if "message is not modified" in text:
            return
        if "message to edit not found" in text or "message can't be edited" in text:
            await post_service.remove_copy(session, copy.id)
            return
        logger.warning("Failed to edit copy %s: %s", copy.id, exc)
    except Exception:
        logger.exception("Failed to edit copy %s", copy.id)


def _build_input_media(message: Message, signature: str):
    if not (message.photo or message.video or message.animation or message.document or message.audio):
        return None

    caption = append_signature(message.html_text if message.caption else None, signature, MAX_CAPTION_LENGTH)
    if message.photo:
        return InputMediaPhoto(media=message.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML)
    if message.video:
        return InputMediaVideo(media=message.video.file_id, caption=caption, parse_mode=ParseMode.HTML)
    if message.animation:
        return InputMediaAnimation(
            media=message.animation.file_id, caption=caption, parse_mode=ParseMode.HTML
        )
    if message.document:
        return InputMediaDocument(
            media=message.document.file_id, caption=caption, parse_mode=ParseMode.HTML
        )
    if message.audio:
        return InputMediaAudio(media=message.audio.file_id, caption=caption, parse_mode=ParseMode.HTML)
    return None
