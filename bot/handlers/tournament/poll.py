from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsTournamentAdmin
from bot.services.tournament import chat as chat_service
from bot.texts import tournament as texts

router = Router(name="tournament_poll")


@router.message(Command("pb_poll_interest"), IsTournamentAdmin())
async def cmd_poll_interest(message: Message, session: AsyncSession, bot: Bot) -> None:
    chat_id = await chat_service.get_registered_chat_id(session)
    if not chat_id:
        await message.answer(texts.NO_CHAT_REGISTERED)
        return

    await bot.send_poll(
        chat_id=chat_id,
        question=texts.POLL_QUESTION,
        options=texts.POLL_OPTIONS,
        is_anonymous=False,
    )
    if message.chat.id != chat_id:
        await message.answer("Опрос отправлен в турнирный чат ✅")
