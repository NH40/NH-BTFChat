from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import CANCEL_WORDS, INVITE_LINK_RE, TME_LINK_RE, USERNAME_RE
from bot.db import Channel
from bot.filters import IsPrivateChat
from bot.keyboards import (
    back_to_menu_kb,
    cancel_add_channel_kb,
    cancel_pending_kb,
    subs_list_kb,
    target_chat_choice_kb,
)
from bot.services import channels as channel_service
from bot.services import pending as pending_service
from bot.services import subscriptions as sub_service
from bot.services import users as user_service
from bot.states import AddChannel
from bot.texts import channels as texts
from bot.utils import safe_edit

router = Router(name="channels")


def extract_username(text: str) -> str | None:
    text = text.strip()
    if INVITE_LINK_RE.search(text):
        return None

    match = TME_LINK_RE.match(text)
    if match:
        return "@" + match.group(1)

    candidate = text[1:] if text.startswith("@") else text
    if USERNAME_RE.match(candidate):
        return "@" + candidate

    return None


@router.callback_query(F.data == "add_channel")
async def cb_add_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddChannel.waiting_username)
    await safe_edit(callback.message, texts.ADD_CHANNEL_PROMPT, reply_markup=cancel_add_channel_kb())
    await callback.answer()


@router.callback_query(F.data == "cancel_add_channel")
async def cb_cancel_add_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback.message, texts.ADD_CHANNEL_CANCELLED, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "cancel_pending")
async def cb_cancel_pending(callback: CallbackQuery, session: AsyncSession) -> None:
    await pending_service.clear_pending(session, callback.from_user.id)
    await safe_edit(callback.message, texts.PENDING_CANCELLED, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.message(AddChannel.waiting_username, IsPrivateChat())
async def process_channel_username(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()

    raw_text = (message.text or "").strip()

    if raw_text.lower() in CANCEL_WORDS:
        await message.answer(texts.ADD_CHANNEL_CANCELLED, reply_markup=back_to_menu_kb())
        return

    username = extract_username(raw_text)

    if username is None:
        if INVITE_LINK_RE.search(raw_text):
            await message.answer(texts.INVITE_LINK_ERROR)
        else:
            await message.answer(texts.UNKNOWN_FORMAT_ERROR)
        return

    try:
        chat = await bot.get_chat(username)
    except Exception:
        await message.answer(texts.CHANNEL_NOT_FOUND_ERROR)
        return

    if chat.type != "channel":
        await message.answer(texts.NOT_A_CHANNEL_ERROR)
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
        texts.admin_rights_prompt(bot_info.username, chat.title),
        reply_markup=cancel_pending_kb(),
    )


async def offer_target_chat(message: Message, session: AsyncSession, db_channel: Channel) -> None:
    target_chats = await sub_service.list_target_chats(session, db_channel.owner_user_id)
    await message.answer(
        texts.offer_target_chat_prompt(db_channel.title),
        reply_markup=target_chat_choice_kb(db_channel.id, target_chats),
    )


@router.callback_query(F.data.startswith("pick_chat:"))
async def cb_pick_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    _, channel_id, target_chat_id = callback.data.split(":")
    await sub_service.create_subscription(session, int(channel_id), int(target_chat_id), callback.from_user.id)
    await safe_edit(callback.message, texts.PICK_CHAT_SUCCESS, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("new_chat:"))
async def cb_new_chat(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    _, channel_id = callback.data.split(":")
    await pending_service.set_pending(
        session, callback.from_user.id, "awaiting_target_chat", {"channel_id": int(channel_id)}
    )
    bot_info = await bot.get_me()
    await safe_edit(
        callback.message,
        texts.new_chat_prompt(bot_info.username),
        reply_markup=cancel_pending_kb(),
    )
    await callback.answer()


async def _render_subs_list(session: AsyncSession, tg_user_id: int) -> tuple[str, object]:
    subs = await sub_service.list_subscriptions_for_user(session, tg_user_id)
    if not subs:
        return texts.NO_SUBS_TEXT, back_to_menu_kb()
    return texts.SUBS_LIST_TEXT, subs_list_kb(subs)


@router.message(Command("list"), IsPrivateChat())
async def cmd_list(message: Message, session: AsyncSession) -> None:
    text, kb = await _render_subs_list(session, message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "list_subs")
async def cb_list_subs(callback: CallbackQuery, session: AsyncSession) -> None:
    text, kb = await _render_subs_list(session, callback.from_user.id)
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("del_sub:"))
async def cb_del_sub(callback: CallbackQuery, session: AsyncSession) -> None:
    _, sub_id = callback.data.split(":")
    await sub_service.delete_subscription(session, int(sub_id), callback.from_user.id)
    text, kb = await _render_subs_list(session, callback.from_user.id)
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer(texts.SUB_DELETED_ANSWER)
