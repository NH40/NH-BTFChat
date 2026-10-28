"""Личка с ботом: /start — кнопки Mini App и гайда (сам гайд — handlers/help)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.handlers.help import CB_HELP
from bot.services import staff

router = Router(name="start")
router.message.filter(F.chat.type == "private")

WELCOME = (
    "<b>BTF — менеджмент команды</b>\n\n"
    "🛡 Модерация чатов · 📣 пересылка из каналов · ✅ задачи, напоминания и отчёты.\n\n"
    "Всё управление — в Mini App. Как работать с ботом — «📖 Гайд» или /help."
)


def _app_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📖 Гайд", callback_data=CB_HELP)]]
    if settings.mini_app_url:
        rows.insert(0, [InlineKeyboardButton(text="📋 Открыть BTF", web_app=WebAppInfo(url=settings.mini_app_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    role = await staff.role_of(session, message.from_user.id)
    if role is None:
        await message.answer("Это бот команды BTF. Доступ к панели — у владельца и админов команды.")
        return
    await message.answer(WELCOME, reply_markup=_app_keyboard())
