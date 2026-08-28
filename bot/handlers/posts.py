import logging

from aiogram import Bot, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services import channels as channel_service
from bot.services import subscriptions as sub_service

router = Router(name="posts")
logger = logging.getLogger(__name__)


@router.channel_post()
async def on_channel_post(message: Message, session: AsyncSession, bot: Bot) -> None:
    db_channel = await channel_service.get_channel_by_tg_id(session, message.chat.id)
    if not db_channel or not db_channel.bot_is_admin:
        return

    target_chat_ids = await sub_service.list_targets_for_channel(session, db_channel.id)
    for tg_chat_id in target_chat_ids:
        try:
            await bot.forward_message(
                chat_id=tg_chat_id, from_chat_id=message.chat.id, message_id=message.message_id
            )
        except Exception:
            logger.exception("Failed to forward message %s to %s", message.message_id, tg_chat_id)
