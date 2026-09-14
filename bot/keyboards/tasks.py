from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constant import DEADLINE_PRESET_LABELS, REMINDER_LABELS, REMINDER_POLICIES


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


def task_card_kb(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполнено", callback_data=f"task_done:{task_id}")
    kb.button(text="🗑 Отменить", callback_data=f"task_cancel:{task_id}")
    kb.adjust(1)
    return kb.as_markup()


def open_tasks_list_kb(tasks, admin_chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for task in tasks:
        label = task.title if len(task.title) <= 40 else task.title[:37] + "…"
        kb.button(text=f"✅ {label}", callback_data=f"task_done:{task.id}")
    kb.button(text="◀️ Назад", callback_data=f"admin_chat:{admin_chat_id}")
    kb.adjust(1)
    return kb.as_markup()
