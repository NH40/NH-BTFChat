"""Личка с ботом: /start, /help — кнопка Mini App для команды."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.services import staff

router = Router(name="start")
router.message.filter(F.chat.type == "private")

HELP = (
    "<b>BTF — менеджмент команды</b>\n\n"
    "🛡 <b>Модерация</b> (в чате, ответом на сообщение или @username / id):\n"
    "/ban [срок] [причина] · /unban · /mute [срок] [причина] · /unmute · /kick · /warn [причина] · /unwarn · /warns\n"
    "Срок: 30m, 2h, 1d, 1w — без срока навсегда.\n\n"
    "📣 <b>Каналы</b> — бот пересылает посты из каналов в выбранные чаты; правки и удаления отслеживает.\n\n"
    "✅ <b>Задачи</b> — доски, дедлайны, подзадачи, повторы и напоминания в чате админов.\n"
    "/tasks — мои задачи (в личке или чате админов).\n\n"
    "Всё настраивается в Mini App."
)


def _app_keyboard() -> InlineKeyboardMarkup | None:
    if not settings.mini_app_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 Открыть BTF", web_app=WebAppInfo(url=settings.mini_app_url))]])


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    role = await staff.role_of(session, message.from_user.id)
    if role is None:
        await message.answer("Это бот команды BTF. Доступ к панели — у владельца и админов команды.")
        return
    await message.answer(HELP, reply_markup=_app_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP, reply_markup=_app_keyboard())
