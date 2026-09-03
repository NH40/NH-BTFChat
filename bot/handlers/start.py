from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsPrivateChat
from bot.keyboards import help_menu_kb, help_section_kb, main_menu_kb
from bot.services import users as user_service
from bot.texts import WELCOME_TEXT
from bot.texts.help import HELP_OVERVIEW, HELP_SECTIONS
from bot.utils import safe_edit

router = Router(name="start")


@router.message(CommandStart(), IsPrivateChat())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    await user_service.get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_OVERVIEW, reply_markup=help_menu_kb())


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await safe_edit(callback.message, HELP_OVERVIEW, reply_markup=help_menu_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("help_section:"))
async def cb_help_section(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    section = HELP_SECTIONS.get(key)
    if section is None:
        await callback.answer()
        return
    _label, text = section
    await safe_edit(callback.message, text, reply_markup=help_section_kb())
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await safe_edit(callback.message, WELCOME_TEXT, reply_markup=main_menu_kb())
    await callback.answer()
