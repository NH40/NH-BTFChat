from aiogram import Bot, Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import target_chat_choice_kb
from bot.services import channels as channel_service
from bot.services import pending as pending_service
from bot.services import subscriptions as sub_service
from bot.services import users as user_service

router = Router(name="membership")

ADMIN_STATUSES = {"administrator", "creator"}
ACTIVE_STATUSES = {"member", "administrator", "creator"}


@router.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated, session: AsyncSession, bot: Bot) -> None:
    if update.chat.type == "channel":
        await handle_channel_membership(update, session, bot)
    elif update.chat.type in ("group", "supergroup"):
        await handle_group_membership(update, session, bot)


async def handle_channel_membership(update: ChatMemberUpdated, session: AsyncSession, bot: Bot) -> None:
    chat = update.chat
    actor = update.from_user
    status = update.new_chat_member.status

    if status not in ADMIN_STATUSES:
        await channel_service.mark_bot_admin(session, chat.id, is_admin=False)
        return

    if actor is None:
        return

    pending = await pending_service.get_pending(session, actor.id)
    if not pending or pending.action != "awaiting_channel_admin" or pending.payload.get("tg_chat_id") != chat.id:
        return

    user = await user_service.get_or_create_user(session, actor.id, actor.username)
    db_channel = await channel_service.upsert_channel(
        session,
        tg_chat_id=chat.id,
        username=chat.username,
        title=chat.title,
        owner_id=user.id,
        bot_is_admin=True,
    )
    await pending_service.clear_pending(session, actor.id)

    target_chats = await sub_service.list_target_chats(session, user.id)
    await bot.send_message(
        actor.id,
        f"Канал «{chat.title}» подключён. Куда пересылать посты?",
        reply_markup=target_chat_choice_kb(db_channel.id, target_chats),
    )


async def handle_group_membership(update: ChatMemberUpdated, session: AsyncSession, bot: Bot) -> None:
    chat = update.chat
    actor = update.from_user
    status = update.new_chat_member.status

    if status not in ACTIVE_STATUSES or actor is None:
        return

    pending = await pending_service.get_pending(session, actor.id)
    if not pending or pending.action != "awaiting_target_chat":
        return

    user = await user_service.get_or_create_user(session, actor.id, actor.username)
    target_chat = await sub_service.upsert_target_chat(
        session,
        tg_chat_id=chat.id,
        title=chat.title or chat.username,
        chat_type=chat.type,
        owner_id=user.id,
    )

    channel_id = pending.payload.get("channel_id")
    await sub_service.create_subscription(session, channel_id, target_chat.id, actor.id)
    await pending_service.clear_pending(session, actor.id)

    await bot.send_message(
        chat.id, "✅ Этот чат подключён. Сюда будут пересылаться новые посты из выбранного канала."
    )
    await bot.send_message(actor.id, "Готово! Посты будут пересылаться в добавленный чат.")
