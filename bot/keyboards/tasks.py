from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constant import (
    DEADLINE_PRESET_LABELS,
    RECURRENCE_LABELS,
    RECURRENCE_OPTIONS,
    REMINDER_LABELS,
    REMINDER_POLICIES,
)


def _short_label(title: str, limit: int = 32) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"


def admin_tasks_menu_kb(admin_chats) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for chat in admin_chats:
        kb.button(text=chat.title or str(chat.tg_chat_id), callback_data=f"admin_chat:{chat.id}")
    kb.button(text="➕ Добавить админ-чат", callback_data="add_admin_chat")
    kb.button(text="🏠 Главное меню", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def admin_chat_menu_kb(admin_chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Новая задача", callback_data=f"new_task:{admin_chat_id}")
    kb.button(text="📋 Открытые задачи", callback_data=f"admin_chat_tasks:{admin_chat_id}")
    kb.button(text="🗑 Отключить чат", callback_data=f"del_admin_chat:{admin_chat_id}")
    kb.button(text="◀️ К списку чатов", callback_data="admin_tasks_menu")
    kb.adjust(1)
    return kb.as_markup()


def cancel_new_task_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="cancel_new_task")
    return kb.as_markup()


def assignee_choice_kb(admins: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for tg_id, name in admins:
        kb.button(text=name, callback_data=f"task_assignee:{tg_id}")
    kb.button(text="❌ Отмена", callback_data="cancel_new_task")
    kb.adjust(1)
    return kb.as_markup()


def deadline_choice_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, label in DEADLINE_PRESET_LABELS.items():
        kb.button(text=label, callback_data=f"task_deadline:{key}")
    kb.button(text="📅 Указать дату", callback_data="task_deadline:custom")
    kb.button(text="Без дедлайна", callback_data="task_deadline:none")
    kb.button(text="❌ Отмена", callback_data="cancel_new_task")
    kb.adjust(1)
    return kb.as_markup()


def reminder_choice_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in REMINDER_POLICIES:
        kb.button(text=REMINDER_LABELS[key], callback_data=f"task_reminder:{key}")
    kb.button(text="❌ Отмена", callback_data="cancel_new_task")
    kb.adjust(1)
    return kb.as_markup()


def recurrence_choice_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in RECURRENCE_OPTIONS:
        kb.button(text=RECURRENCE_LABELS[key], callback_data=f"task_recurrence:{key}")
    kb.button(text="❌ Отмена", callback_data="cancel_new_task")
    kb.adjust(1)
    return kb.as_markup()


def _task_cb(action: str, task_id: int, origin: str | None, admin_chat_id: int | None) -> str:
    return f"{action}:{task_id}:{origin or '-'}:{admin_chat_id or 0}"


def task_card_kb(
    task_id: int, origin: str | None = None, admin_chat_id: int | None = None
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполнено", callback_data=_task_cb("task_done", task_id, origin, admin_chat_id))
    kb.button(text="❌ Не выполнено", callback_data=_task_cb("task_missed", task_id, origin, admin_chat_id))
    kb.button(text="🗑 Отменить", callback_data=_task_cb("task_cancel", task_id, origin, admin_chat_id))
    if origin:
        kb.button(text="◀️ К списку", callback_data=f"task_back:{origin}:{admin_chat_id or 0}")
    kb.adjust(1)
    return kb.as_markup()


def task_resolved_kb(
    task_id: int, origin: str | None = None, admin_chat_id: int | None = None
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Вернуть в работу", callback_data=_task_cb("task_reopen", task_id, origin, admin_chat_id))
    if origin:
        kb.button(text="◀️ К списку", callback_data=f"task_back:{origin}:{admin_chat_id or 0}")
    kb.adjust(1)
    return kb.as_markup()


def open_tasks_list_kb(tasks, admin_chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, task in enumerate(tasks, start=1):
        kb.button(
            text=f"🔎 {index}. {_short_label(task.title)}",
            callback_data=f"task_view:{task.id}:all:{admin_chat_id}",
        )
    kb.button(text="◀️ Назад", callback_data=f"admin_chat:{admin_chat_id}")
    kb.adjust(1)
    return kb.as_markup()


def task_picker_kb(tasks, admin_chat_id: int, origin: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, task in enumerate(tasks, start=1):
        kb.button(
            text=f"🔎 {index}. {_short_label(task.title)}",
            callback_data=f"task_view:{task.id}:{origin}:{admin_chat_id}",
        )
    kb.adjust(1)
    return kb.as_markup()


def history_list_kb(tasks) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, task in enumerate(tasks, start=1):
        kb.button(text=f"🔄 {index}. {_short_label(task.title)}", callback_data=f"task_reopen:{task.id}")
    kb.adjust(1)
    return kb.as_markup()
