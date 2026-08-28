from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import main_menu_kb
from bot.services import users as user_service

router = Router(name="start")

WELCOME_TEXT = (
    "Привет! Я пересылаю новые посты из Telegram-каналов в чат, который ты выберешь.\n\n"
    "Как это работает:\n"
    "1. Добавляешь канал (пришли его @username).\n"
    "2. Добавляешь меня администратором в этот канал — иначе Telegram не даёт мне видеть посты.\n"
    "3. Добавляешь меня в чат или группу, куда пересылать посты — и всё готово."
)

HELP_TEXT = (
    "Команды:\n"
    "/start — главное меню\n"
    "/list — мои правила пересылки\n\n"
    "Чтобы добавить канал — нажми «Добавить канал» и пришли его @username."
)


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, session: AsyncSession) -> None:
    await user_service.get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.message.answer(HELP_TEXT)
    await callback.answer()
