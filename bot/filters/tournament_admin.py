from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.tournament import chat as chat_service


class IsTournamentAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession) -> bool:
        user = event.from_user
        if user is None:
            return False
        return await chat_service.is_admin(session, user.id)
