from __future__ import annotations

import datetime as dt

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import CANCEL_WORDS, DEADLINE_PRESETS, MAX_TASK_TITLE_LENGTH
from bot.filters import IsPrivateChat
from bot.keyboards import (
    admin_chat_menu_kb,
    admin_tasks_menu_kb,
    assignee_choice_kb,
    back_to_menu_kb,
    cancel_new_task_kb,
    deadline_choice_kb,
    open_tasks_list_kb,
    reminder_choice_kb,
    task_card_kb,
)
from bot.services import admin_chats as admin_chat_service
from bot.services import pending as pending_service
from bot.services import tasks as task_service
from bot.services import users as user_service
from bot.states import NewTask
from bot.texts import tasks as texts
from bot.utils import parse_deadline_input, safe_edit

router = Router(name="tasks")


async def _render_admin_tasks_menu(session: AsyncSession, tg_user_id: int) -> tuple[str, object]:
    chats = await admin_chat_service.list_admin_chats_for_owner(session, tg_user_id)
    if not chats:
        return texts.NO_ADMIN_CHATS_TEXT, admin_tasks_menu_kb(chats)
    return texts.ADMIN_TASKS_MENU_TEXT, admin_tasks_menu_kb(chats)


@router.callback_query(F.data == "admin_tasks_menu")
async def cb_admin_tasks_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    await user_service.get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    text, kb = await _render_admin_tasks_menu(session, callback.from_user.id)
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "add_admin_chat")
async def cb_add_admin_chat(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await pending_service.set_pending(session, callback.from_user.id, "awaiting_admin_chat", {})
    bot_info = await bot.get_me()
    await safe_edit(
        callback.message,
        texts.offer_admin_chat_prompt(bot_info.username),
        reply_markup=cancel_new_task_kb(),
    )
    await callback.answer()


async def _get_owned_admin_chat(callback: CallbackQuery, session: AsyncSession, admin_chat_id: int):
    admin_chat = await admin_chat_service.get_admin_chat(session, admin_chat_id)
    if not admin_chat or admin_chat.owner.tg_user_id != callback.from_user.id:
        await callback.answer("Чат не найден.", show_alert=True)
        return None
    return admin_chat


@router.callback_query(F.data.startswith("admin_chat:"))
async def cb_admin_chat_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_chat_id = int(callback.data.split(":")[1])
    admin_chat = await _get_owned_admin_chat(callback, session, admin_chat_id)
    if not admin_chat:
        return
    await safe_edit(
        callback.message,
        texts.admin_chat_menu_text(admin_chat.title),
        reply_markup=admin_chat_menu_kb(admin_chat.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_admin_chat:"))
async def cb_del_admin_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_chat_id = int(callback.data.split(":")[1])
    deleted = await admin_chat_service.delete_admin_chat(session, admin_chat_id, callback.from_user.id)
    if not deleted:
        await callback.answer("Чат не найден.", show_alert=True)
        return
    text, kb = await _render_admin_tasks_menu(session, callback.from_user.id)
    await safe_edit(callback.message, texts.ADMIN_CHAT_DELETED + "\n\n" + text, reply_markup=kb)
    await callback.answer()


async def _render_open_tasks(session: AsyncSession, admin_chat_id: int) -> tuple[str, object]:
    open_tasks = await task_service.list_open_tasks(session, admin_chat_id)
    if not open_tasks:
        return texts.NO_OPEN_TASKS_TEXT, admin_chat_menu_kb(admin_chat_id)
    lines = [texts.OPEN_TASKS_LIST_TEXT, ""]
    lines.extend(texts.open_task_list_item(task) for task in open_tasks)
    return "\n".join(lines), open_tasks_list_kb(open_tasks, admin_chat_id)


@router.callback_query(F.data.startswith("admin_chat_tasks:"))
async def cb_admin_chat_tasks(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_chat_id = int(callback.data.split(":")[1])
    admin_chat = await _get_owned_admin_chat(callback, session, admin_chat_id)
    if not admin_chat:
        return
    text, kb = await _render_open_tasks(session, admin_chat_id)
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("new_task:"))
async def cb_new_task_start(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext
) -> None:
    admin_chat_id = int(callback.data.split(":")[1])
    admin_chat = await _get_owned_admin_chat(callback, session, admin_chat_id)
    if not admin_chat:
        return

    members = await bot.get_chat_administrators(admin_chat.tg_chat_id)
    admins = [
        (m.user.id, m.user.full_name or (f"@{m.user.username}" if m.user.username else str(m.user.id)))
        for m in members
        if not m.user.is_bot
    ]
    if not admins:
        await callback.answer(texts.NO_ADMINS_FOUND, show_alert=True)
        return

    await state.update_data(admin_chat_id=admin_chat_id, admins=dict(admins))
    await safe_edit(callback.message, texts.CHOOSE_ASSIGNEE_TEXT, reply_markup=assignee_choice_kb(admins))
    await callback.answer()


@router.callback_query(F.data.startswith("task_assignee:"))
async def cb_task_assignee(callback: CallbackQuery, state: FSMContext) -> None:
    assignee_tg_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    if "admin_chat_id" not in data:
        await callback.answer()
        return
    assignee_name = data.get("admins", {}).get(assignee_tg_id) or data.get("admins", {}).get(
        str(assignee_tg_id), "админ"
    )
    await state.update_data(assignee_tg_id=assignee_tg_id, assignee_name=assignee_name)
    await state.set_state(NewTask.waiting_title)
    await safe_edit(callback.message, texts.ASK_TASK_TITLE_TEXT, reply_markup=cancel_new_task_kb())
    await callback.answer()


@router.message(NewTask.waiting_title, IsPrivateChat())
async def process_task_title(message: Message, state: FSMContext) -> None:
    raw_text = (message.text or "").strip()
    if raw_text.lower() in CANCEL_WORDS:
        await state.clear()
        await message.answer(texts.NEW_TASK_CANCELLED, reply_markup=back_to_menu_kb())
        return
    if not raw_text:
        await message.answer(texts.ASK_TASK_TITLE_TEXT, reply_markup=cancel_new_task_kb())
        return

    title = raw_text[:MAX_TASK_TITLE_LENGTH]
    await state.update_data(title=title)
    await state.set_state(None)
    await message.answer(texts.ASK_DEADLINE_TEXT, reply_markup=deadline_choice_kb())


@router.callback_query(F.data.startswith("task_deadline:"))
async def cb_task_deadline(callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if "title" not in data:
        await callback.answer()
        return

    if key == "custom":
        await state.set_state(NewTask.waiting_custom_deadline)
        await safe_edit(callback.message, texts.ASK_CUSTOM_DEADLINE_TEXT, reply_markup=cancel_new_task_kb())
        await callback.answer()
        return

    if key == "none":
        await callback.answer()
        await _finalize_task(callback.message, session, bot, state, callback.from_user.id, "none")
        return

    offset = DEADLINE_PRESETS.get(key)
    if offset is None:
        await callback.answer()
        return

    deadline = dt.datetime.utcnow() + offset
    await state.update_data(deadline=deadline.isoformat())
    await safe_edit(callback.message, texts.ASK_REMINDER_TEXT, reply_markup=reminder_choice_kb())
    await callback.answer()


@router.message(NewTask.waiting_custom_deadline, IsPrivateChat())
async def process_custom_deadline(message: Message, state: FSMContext) -> None:
    raw_text = (message.text or "").strip()
    if raw_text.lower() in CANCEL_WORDS:
        await state.clear()
        await message.answer(texts.NEW_TASK_CANCELLED, reply_markup=back_to_menu_kb())
        return

    deadline = parse_deadline_input(raw_text)
    if deadline is None:
        await message.answer(texts.BAD_DEADLINE_FORMAT, reply_markup=cancel_new_task_kb())
        return

    await state.update_data(deadline=deadline.isoformat())
    await state.set_state(None)
    await message.answer(texts.ASK_REMINDER_TEXT, reply_markup=reminder_choice_kb())


@router.callback_query(F.data.startswith("task_reminder:"))
async def cb_task_reminder(callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    reminder_policy = callback.data.split(":", 1)[1]
    await callback.answer()
    await _finalize_task(callback.message, session, bot, state, callback.from_user.id, reminder_policy)


async def _finalize_task(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
    owner_tg_id: int,
    reminder_policy: str,
) -> None:
    data = await state.get_data()
    admin_chat_id = data.get("admin_chat_id")
    if admin_chat_id is None:
        return

    admin_chat = await admin_chat_service.get_admin_chat(session, admin_chat_id)
    if not admin_chat:
        await state.clear()
        await safe_edit(message, texts.NEW_TASK_CANCELLED, reply_markup=back_to_menu_kb())
        return

    deadline_raw = data.get("deadline")
    deadline = dt.datetime.fromisoformat(deadline_raw) if deadline_raw else None

    task = await task_service.create_task(
        session,
        admin_chat_id=admin_chat_id,
        created_by_tg_id=owner_tg_id,
        assignee_tg_id=data["assignee_tg_id"],
        assignee_name=data.get("assignee_name"),
        title=data["title"],
        deadline=deadline,
        reminder_policy=reminder_policy,
    )

    sent = await bot.send_message(
        admin_chat.tg_chat_id, texts.task_card_text(task), reply_markup=task_card_kb(task.id)
    )
    await task_service.set_task_message(session, task.id, sent.message_id)
    await state.clear()

    await safe_edit(message, texts.TASK_CREATED_OWNER, reply_markup=admin_chat_menu_kb(admin_chat.id))


@router.callback_query(F.data == "cancel_new_task")
async def cb_cancel_new_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback.message, texts.NEW_TASK_CANCELLED, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await _resolve_task(callback, session, bot, mark_done=True)


@router.callback_query(F.data.startswith("task_cancel:"))
async def cb_task_cancel(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await _resolve_task(callback, session, bot, mark_done=False)


async def _resolve_task(callback: CallbackQuery, session: AsyncSession, bot: Bot, *, mark_done: bool) -> None:
    task_id = int(callback.data.split(":")[1])
    task = await task_service.get_task(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    admin_chat = task.admin_chat
    is_owner = admin_chat is not None and admin_chat.owner.tg_user_id == callback.from_user.id
    is_assignee = task.assignee_tg_id == callback.from_user.id

    if mark_done:
        if not (is_owner or is_assignee):
            await callback.answer(texts.NOT_ALLOWED_DONE, show_alert=True)
            return
        if task.status == "open":
            task = await task_service.mark_done(session, task_id)
        suffix = texts.task_done_suffix()
        answer_text = texts.TASK_DONE_ANSWER
    else:
        if not is_owner:
            await callback.answer(texts.NOT_ALLOWED_CANCEL, show_alert=True)
            return
        if task.status == "open":
            task = await task_service.cancel_task(session, task_id)
        suffix = texts.task_cancelled_suffix()
        answer_text = texts.TASK_CANCEL_ANSWER

    if admin_chat and task.chat_message_id:
        try:
            await bot.edit_message_text(
                chat_id=admin_chat.tg_chat_id,
                message_id=task.chat_message_id,
                text=texts.task_card_text(task) + suffix,
            )
        except Exception:
            pass

    if admin_chat and callback.message.chat.id != admin_chat.tg_chat_id:
        text, kb = await _render_open_tasks(session, admin_chat.id)
        await safe_edit(callback.message, text, reply_markup=kb)

    await callback.answer(answer_text)


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return
    text, kb = await _render_open_tasks(session, admin_chat.id)
    await message.answer(text, reply_markup=kb)
