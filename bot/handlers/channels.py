from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import subs_list_kb, target_chat_choice_kb
from bot.models import Channel
from bot.services import channels as channel_service
from bot.services import pending as pending_service
from bot.services import subscriptions as sub_service
from bot.services import users as user_service
from bot.states import AddChannel

router = Router(name="channels")


@router.callback_query(F.data == "add_channel")
async def cb_add_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddChannel.waiting_username)
    await callback.message.answer("Пришли @username канала, который нужно подключить.")
    await callback.answer()


@router.message(AddChannel.waiting_username, F.chat.type == "private")
async def process_channel_username(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()

    username = (message.text or "").strip()
    if not username.startswith("@"):
        username = "@" + username

    try:
        chat = await bot.get_chat(username)
    except Exception:
        await message.answer("Не могу найти такой канал. Проверь юзернейм и убедись, что канал публичный.")
        return

    if chat.type != "channel":
        await message.answer("Это не канал. Пришли юзернейм именно канала.")
        return

    user = await user_service.get_or_create_user(session, message.from_user.id, message.from_user.username)

    member = None
    try:
        member = await bot.get_chat_member(chat.id, bot.id)
    except Exception:
        pass

    if member and member.status in ("administrator", "creator"):
        db_channel = await channel_service.upsert_channel(
            session,
            tg_chat_id=chat.id,
            username=chat.username,
            title=chat.title,
            owner_id=user.id,
            bot_is_admin=True,
        )
        await offer_target_chat(message, session, db_channel)
        return

    await pending_service.set_pending(
        session,
        message.from_user.id,
        "awaiting_channel_admin",
        {"tg_chat_id": chat.id, "username": chat.username, "title": chat.title},
    )
    bot_info = await bot.get_me()
    await message.answer(
        f"Добавь меня (@{bot_info.username}) администратором в канал «{chat.title}» "
        "с правом публикации сообщений — как только это произойдёт, я подключу канал автоматически."
    )


async def offer_target_chat(message: Message, session: AsyncSession, db_channel: Channel) -> None:
    target_chats = await sub_service.list_target_chats(session, db_channel.owner_user_id)
    await message.answer(
        f"Канал «{db_channel.title}» подключён. Куда пересылать посты?",
        reply_markup=target_chat_choice_kb(db_channel.id, target_chats),
    )


@router.callback_query(F.data.startswith("pick_chat:"))
async def cb_pick_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    _, channel_id, target_chat_id = callback.data.split(":")
    await sub_service.create_subscription(session, int(channel_id), int(target_chat_id), callback.from_user.id)
    await callback.message.answer("Готово! Посты из этого канала будут пересылаться в выбранный чат.")
    await callback.answer()


@router.callback_query(F.data.startswith("new_chat:"))
async def cb_new_chat(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    _, channel_id = callback.data.split(":")
    await pending_service.set_pending(
        session, callback.from_user.id, "awaiting_target_chat", {"channel_id": int(channel_id)}
    )
    bot_info = await bot.get_me()
    await callback.message.answer(
        f"Добавь меня (@{bot_info.username}) в чат или группу, куда нужно пересылать посты — "
        "как только это произойдёт, я подключу его автоматически."
    )
    await callback.answer()


@router.message(Command("list"), F.chat.type == "private")
async def cmd_list(message: Message, session: AsyncSession) -> None:
    subs = await sub_service.list_subscriptions_for_user(session, message.from_user.id)
    if not subs:
        await message.answer("Пока нет ни одного правила пересылки.")
        return
    await message.answer("Твои правила пересылки:", reply_markup=subs_list_kb(subs))


@router.callback_query(F.data == "list_subs")
async def cb_list_subs(callback: CallbackQuery, session: AsyncSession) -> None:
    subs = await sub_service.list_subscriptions_for_user(session, callback.from_user.id)
    if not subs:
        await callback.message.answer("Пока нет ни одного правила пересылки.")
    else:
        await callback.message.answer("Твои правила пересылки:", reply_markup=subs_list_kb(subs))
    await callback.answer()


@router.callback_query(F.data.startswith("del_sub:"))
async def cb_del_sub(callback: CallbackQuery, session: AsyncSession) -> None:
    _, sub_id = callback.data.split(":")
    await sub_service.delete_subscription(session, int(sub_id), callback.from_user.id)
    await callback.message.answer("Правило удалено.")
    await callback.answer()
