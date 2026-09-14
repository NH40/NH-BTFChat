from aiogram import Bot, Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import admin_chat_menu_kb, back_to_menu_kb, target_chat_choice_kb
from bot.services import admin_chats as admin_chat_service
from bot.services import channels as channel_service
from bot.services import pending as pending_service
from bot.services import subscriptions as sub_service
from bot.services import users as user_service
from bot.texts import membership as texts
from bot.texts import tasks as task_texts
from bot.texts.channels import offer_target_chat_prompt

router = Router(name="membership")

ADMIN_STATUSES = {"administrator", "creator"}
ACTIVE_STATUSES = {"member", "administrator", "creator"}
GROUP_PENDING_ACTIONS = {"awaiting_target_chat", "awaiting_admin_chat"}


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
        offer_target_chat_prompt(chat.title),
        reply_markup=target_chat_choice_kb(db_channel.id, target_chats),
    )


async def handle_group_membership(update: ChatMemberUpdated, session: AsyncSession, bot: Bot) -> None:
    chat = update.chat
    actor = update.from_user
    status = update.new_chat_member.status

    if status not in ACTIVE_STATUSES or actor is None:
        return

    pending = await pending_service.get_pending(session, actor.id)
    if not pending or pending.action not in GROUP_PENDING_ACTIONS:
        return

    user = await user_service.get_or_create_user(session, actor.id, actor.username)

    if pending.action == "awaiting_admin_chat":
        admin_chat = await admin_chat_service.upsert_admin_chat(
            session, tg_chat_id=chat.id, title=chat.title or chat.username, owner_id=user.id
        )
        await pending_service.clear_pending(session, actor.id)
        await bot.send_message(chat.id, task_texts.ADMIN_CHAT_CONNECTED_IN_CHAT)
        await bot.send_message(
            actor.id,
            task_texts.ADMIN_CHAT_CONNECTED_OWNER,
            reply_markup=admin_chat_menu_kb(admin_chat.id),
        )
        return

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

    await bot.send_message(chat.id, texts.TARGET_CHAT_CONNECTED)
    await bot.send_message(actor.id, texts.OWNER_TARGET_CONNECTED, reply_markup=back_to_menu_kb())
