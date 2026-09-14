from __future__ import annotations

import datetime as dt

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import CANCEL_WORDS, DEADLINE_PRESETS, MAX_ROLE_LENGTH, MAX_TASK_TITLE_LENGTH
from bot.filters import IsPrivateChat
from bot.keyboards import (
    admin_chat_menu_kb,
    admin_tasks_menu_kb,
    assignee_choice_kb,
    back_to_menu_kb,
    cancel_new_task_kb,
    deadline_choice_kb,
    history_list_kb,
    open_tasks_list_kb,
    recurrence_choice_kb,
    reminder_choice_kb,
    task_card_kb,
    task_picker_kb,
    task_resolved_kb,
)
from bot.services import admin_chats as admin_chat_service
from bot.services import admin_roles as admin_role_service
from bot.services import pending as pending_service
from bot.services import task_events as task_event_service
from bot.services import tasks as task_service
from bot.services import users as user_service
from bot.states import NewTask
from bot.texts import tasks as texts
from bot.utils import parse_deadline_input, safe_edit

router = Router(name="tasks")


def _display_name(user) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


async def _chat_admins(bot: Bot, tg_chat_id: int) -> list[tuple[int, str]]:
    members = await bot.get_chat_administrators(tg_chat_id)
    return [(m.user.id, _display_name(m.user)) for m in members if not m.user.is_bot]


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
    lines.extend(texts.open_task_list_item(i, task) for i, task in enumerate(open_tasks, start=1))
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


# ---------------------------------------------------------------------------
# Owner wizard: full task with assignee, free-text title, deadline, reminder
# policy and recurrence. Always started from the private chat menu.
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("new_task:"))
async def cb_new_task_start(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext
) -> None:
    admin_chat_id = int(callback.data.split(":")[1])
    admin_chat = await _get_owned_admin_chat(callback, session, admin_chat_id)
    if not admin_chat:
        return

    admins = await _chat_admins(bot, admin_chat.tg_chat_id)
    if not admins:
        await callback.answer(texts.NO_ADMINS_FOUND, show_alert=True)
        return

    await state.update_data(admin_chat_id=admin_chat_id, admins=dict(admins), kind="task")
    await safe_edit(callback.message, texts.CHOOSE_ASSIGNEE_TEXT, reply_markup=assignee_choice_kb(admins))
    await callback.answer()


@router.callback_query(F.data.startswith("task_assignee:"))
async def cb_task_assignee(callback: CallbackQuery, state: FSMContext) -> None:
    assignee_tg_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    if "admin_chat_id" not in data:
        await callback.answer()
        return
    admins = data.get("admins", {})
    assignee_name = admins.get(assignee_tg_id) or admins.get(str(assignee_tg_id), "админ")
    await state.update_data(assignee_tg_id=assignee_tg_id, assignee_name=assignee_name)
    await state.set_state(NewTask.waiting_title)
    await safe_edit(callback.message, texts.ASK_TASK_TITLE_TEXT, reply_markup=cancel_new_task_kb())
    await callback.answer()


@router.message(NewTask.waiting_title)
async def process_task_title(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
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
    data = await state.get_data()

    if data.get("kind") == "order":
        # Orders are ad-hoc requests: no deadline/reminder/recurrence wizard.
        await state.update_data(deadline=None, recurrence="none")
        await state.set_state(None)
        await _finalize_task(message, session, bot, state, message.from_user.id, "none")
        return

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
        await state.update_data(deadline=None, recurrence="none")
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
async def cb_task_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    reminder_policy = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if "title" not in data:
        await callback.answer()
        return
    await state.update_data(reminder_policy=reminder_policy)
    await safe_edit(callback.message, texts.ASK_RECURRENCE_TEXT, reply_markup=recurrence_choice_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("task_recurrence:"))
async def cb_task_recurrence(callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    recurrence = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if "title" not in data:
        await callback.answer()
        return
    await callback.answer()
    await state.update_data(recurrence=recurrence)
    await _finalize_task(
        callback.message, session, bot, state, callback.from_user.id, data.get("reminder_policy", "none")
    )


async def _finalize_task(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
    creator_tg_id: int,
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
    kind = data.get("kind", "task")

    creator_name = None
    try:
        creator_member = await bot.get_chat_member(admin_chat.tg_chat_id, creator_tg_id)
        creator_name = _display_name(creator_member.user)
    except Exception:
        pass

    task = await task_service.create_task(
        session,
        admin_chat_id=admin_chat_id,
        created_by_tg_id=creator_tg_id,
        created_by_name=creator_name,
        assignee_tg_id=data["assignee_tg_id"],
        assignee_name=data.get("assignee_name"),
        title=data["title"],
        deadline=deadline,
        reminder_policy=reminder_policy,
        recurrence=data.get("recurrence", "none"),
        kind=kind,
    )

    sent = await bot.send_message(
        admin_chat.tg_chat_id, texts.task_card_text(task), reply_markup=task_card_kb(task.id)
    )
    await task_service.set_task_message(session, task.id, sent.message_id)
    await state.clear()

    confirm_text = texts.ORDER_CREATED_TEXT if kind == "order" else texts.TASK_CREATED_OWNER
    if message.chat.id == admin_chat.tg_chat_id:
        # Order flow: the wizard ran inline in the group chat itself.
        await message.answer(confirm_text)
    else:
        await safe_edit(message, confirm_text, reply_markup=admin_chat_menu_kb(admin_chat.id))


@router.callback_query(F.data == "cancel_new_task")
async def cb_cancel_new_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback.message, texts.NEW_TASK_CANCELLED, reply_markup=back_to_menu_kb())
    await callback.answer()


# ---------------------------------------------------------------------------
# Orders: any chat member can request a task from a specific assignee.
# ---------------------------------------------------------------------------


@router.message(Command("order"))
async def cmd_order(message: Message, session: AsyncSession, bot: Bot, state: FSMContext) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return

    admins = await _chat_admins(bot, admin_chat.tg_chat_id)
    if not admins:
        await message.reply(texts.NO_ADMINS_FOUND)
        return

    await state.update_data(admin_chat_id=admin_chat.id, admins=dict(admins), kind="order")
    await message.reply(texts.CHOOSE_ASSIGNEE_TEXT, reply_markup=assignee_choice_kb(admins))


@router.message(Command("orders"))
async def cmd_orders(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return

    orders = await task_service.list_open_tasks(session, admin_chat.id, kind="order")
    if not orders:
        await message.answer(texts.NO_OPEN_ORDERS_TEXT)
        return
    lines = [texts.OPEN_ORDERS_LIST_TEXT, ""]
    lines.extend(texts.open_task_list_item(i, task) for i, task in enumerate(orders, start=1))
    await message.answer("\n".join(lines), reply_markup=task_picker_kb(orders))


# ---------------------------------------------------------------------------
# Personal views and history.
# ---------------------------------------------------------------------------


async def _reply_my_tasks(message: Message, session: AsyncSession) -> None:
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return

    my_tasks = await task_service.list_open_tasks_for_assignee(session, admin_chat.id, message.from_user.id)
    if not my_tasks:
        await message.answer(texts.NO_MY_TASKS_TEXT)
        return
    lines = [texts.MY_TASKS_LIST_TEXT, ""]
    lines.extend(texts.my_task_list_item(i, task) for i, task in enumerate(my_tasks, start=1))
    await message.answer("\n".join(lines), reply_markup=task_picker_kb(my_tasks))


@router.message(Command("tasks", "mytasks"))
async def cmd_mytasks(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    await _reply_my_tasks(message, session)


@router.message(Command("done"))
async def cmd_history(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return

    resolved = await task_service.list_recent_resolved(session, admin_chat.id)
    if not resolved:
        await message.answer(texts.NO_HISTORY_TEXT)
        return
    lines = [texts.HISTORY_LIST_TEXT, ""]
    lines.extend(texts.history_list_item(i, task) for i, task in enumerate(resolved, start=1))
    await message.answer("\n".join(lines), reply_markup=history_list_kb(resolved))


# ---------------------------------------------------------------------------
# Responsibilities (persistent role description per admin).
# ---------------------------------------------------------------------------


@router.message(Command("role"))
async def cmd_role(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return
    role = await admin_role_service.get_role(session, admin_chat.id, message.from_user.id)
    await message.reply(texts.role_text(role.description if role else None))


@router.message(Command("setrole"))
async def cmd_setrole(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return
    if admin_chat.owner.tg_user_id != message.from_user.id:
        await message.reply(texts.NOT_ALLOWED_SETROLE)
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(texts.SETROLE_NEEDS_REPLY_TEXT)
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply(texts.SETROLE_USAGE_TEXT)
        return

    target = message.reply_to_message.from_user
    description = parts[1].strip()[:MAX_ROLE_LENGTH]
    await admin_role_service.set_role(session, admin_chat.id, target.id, description)
    await message.reply(texts.role_set_answer(_display_name(target)))


# ---------------------------------------------------------------------------
# Task/order detail view and resolution: view, done, missed, cancel, reopen.
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("task_view:"))
async def cb_task_view(callback: CallbackQuery, session: AsyncSession) -> None:
    task_id = int(callback.data.split(":")[1])
    task = await task_service.get_task(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return
    kb = task_card_kb(task.id) if task.status == "open" else task_resolved_kb(task.id)
    await callback.message.reply(texts.task_card_text(task), reply_markup=kb)
    await callback.answer()


async def _update_task_message(callback: CallbackQuery, bot: Bot, task, card_text: str, card_kb) -> None:
    admin_chat = task.admin_chat
    if admin_chat and task.chat_message_id and task.chat_message_id != callback.message.message_id:
        try:
            await bot.edit_message_text(
                chat_id=admin_chat.tg_chat_id,
                message_id=task.chat_message_id,
                text=card_text,
                reply_markup=card_kb,
            )
        except Exception:
            pass
    try:
        await safe_edit(callback.message, card_text, reply_markup=card_kb)
    except Exception:
        pass


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await _apply_task_action(callback, session, bot, action="done")


@router.callback_query(F.data.startswith("task_missed:"))
async def cb_task_missed(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await _apply_task_action(callback, session, bot, action="missed")


@router.callback_query(F.data.startswith("task_cancel:"))
async def cb_task_cancel(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await _apply_task_action(callback, session, bot, action="cancel")


async def _apply_task_action(callback: CallbackQuery, session: AsyncSession, bot: Bot, *, action: str) -> None:
    task_id = int(callback.data.split(":")[1])
    task = await task_service.get_task(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    admin_chat = task.admin_chat
    is_owner = admin_chat is not None and admin_chat.owner.tg_user_id == callback.from_user.id
    is_assignee = task.assignee_tg_id == callback.from_user.id

    if action == "cancel":
        if not is_owner:
            await callback.answer(texts.NOT_ALLOWED_CANCEL, show_alert=True)
            return
    elif not (is_owner or is_assignee):
        await callback.answer(texts.NOT_ALLOWED_DONE, show_alert=True)
        return

    if task.status == "open":
        if action == "done":
            task = await task_service.mark_done(session, task_id)
        elif action == "missed":
            task = await task_service.mark_missed(session, task_id)
        else:
            task = await task_service.cancel_task(session, task_id)

    if task.status == "open":
        # Recurring task rolled forward to the next cycle instead of closing.
        answer_text = texts.TASK_RECURRED_ANSWER
    else:
        answer_text = {
            "done": texts.TASK_DONE_ANSWER,
            "missed": texts.TASK_MISSED_ANSWER,
            "cancelled": texts.TASK_CANCEL_ANSWER,
        }[task.status]

    card_kb = task_card_kb(task.id) if task.status == "open" else task_resolved_kb(task.id)
    await _update_task_message(callback, bot, task, texts.task_card_text(task), card_kb)
    await callback.answer(answer_text)


@router.callback_query(F.data.startswith("task_reopen:"))
async def cb_task_reopen(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    task_id = int(callback.data.split(":")[1])
    task = await task_service.get_task(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    admin_chat = task.admin_chat
    is_owner = admin_chat is not None and admin_chat.owner.tg_user_id == callback.from_user.id
    is_assignee = task.assignee_tg_id == callback.from_user.id
    if not (is_owner or is_assignee):
        await callback.answer(texts.NOT_ALLOWED_DONE, show_alert=True)
        return

    task = await task_service.reopen_task(session, task_id)
    await _update_task_message(callback, bot, task, texts.task_card_text(task), task_card_kb(task.id))
    await callback.answer(texts.TASK_REOPEN_ANSWER)


@router.message(Command("alltasks"))
async def cmd_all_tasks(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return
    text, kb = await _render_open_tasks(session, admin_chat.id)
    await message.answer(text, reply_markup=kb)


# ---------------------------------------------------------------------------
# Owner-only stats: who completed how much, and how much on time.
# ---------------------------------------------------------------------------


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    admin_chat = await admin_chat_service.get_admin_chat_by_tg_id(session, message.chat.id)
    if not admin_chat:
        return
    if admin_chat.owner.tg_user_id != message.from_user.id:
        await message.reply(texts.NOT_ALLOWED_STATS)
        return

    rows = await task_event_service.get_stats(session, admin_chat.id)
    await message.answer(texts.stats_text(rows))
