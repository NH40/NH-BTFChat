from __future__ import annotations

from bot.constant import RECURRENCE_LABELS, REMINDER_LABELS
from bot.db import Task
from bot.utils.time import format_deadline

ADMIN_TASKS_MENU_TEXT = "🗂 <b>Задачи админам</b>\n\nЧаты, где ты можешь ставить задачи админам:"
NO_ADMIN_CHATS_TEXT = (
    "Пока не подключено ни одного чата с админами.\n\n"
    "Нажми «➕ Добавить админ-чат», чтобы подключить чат, где будешь ставить задачи."
)

ADD_ADMIN_CHAT_CANCELLED = "Добавление админ-чата отменено."
ADMIN_CHAT_CONNECTED_IN_CHAT = "✅ Этот чат подключён как чат админов. Здесь будут появляться задачи."
ADMIN_CHAT_CONNECTED_OWNER = "✅ Готово! Теперь можешь ставить в этом чате задачи админам."

ADMIN_CHAT_DELETED = "🗑 Админ-чат отключён. Задачи в нём больше не отслеживаются."

NEW_TASK_CANCELLED = "Создание задачи отменено."
NO_ADMINS_FOUND = (
    "Не нашёл ни одного администратора в этом чате (кроме ботов). "
    "Сначала выдай нужным людям права администратора в Telegram."
)
CHOOSE_ASSIGNEE_TEXT = "Кому ставим задачу?"
ASK_TASK_TITLE_TEXT = "Напиши текст задачи (можно с описанием, списком и т.д.)."
ASK_DEADLINE_TEXT = "Когда дедлайн?"
ASK_CUSTOM_DEADLINE_TEXT = (
    "Пришли дату дедлайна: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code> или коротко <code>ДД.ММ</code> "
    "(время московское). Например <code>20.09.2026 18:00</code> или просто <code>13.03</code> "
    "— год возьму текущий (или следующий, если дата уже прошла), а время 00:00, если не указано."
)
BAD_DEADLINE_FORMAT = "Не понял дату. Пришли в формате ДД.ММ.ГГГГ ЧЧ:ММ или хотя бы ДД.ММ, например 13.03."
ASK_REMINDER_TEXT = "Как напоминать о дедлайне?"
ASK_RECURRENCE_TEXT = "Это разовая задача или она повторяется по расписанию?"

TASK_CREATED_OWNER = "✅ Задача создана и отправлена в чат."
ORDER_CREATED_TEXT = "✅ Заказ отправлен в чат."

NO_OPEN_TASKS_TEXT = "В этом чате пока нет открытых задач."
OPEN_TASKS_LIST_TEXT = "📋 Открытые задачи:"

NO_OPEN_ORDERS_TEXT = "Открытых заказов пока нет."
OPEN_ORDERS_LIST_TEXT = "📦 Очередь заказов:"

NO_MY_TASKS_TEXT = "На тебе сейчас нет открытых задач."
MY_TASKS_LIST_TEXT = "🙋 Твои открытые задачи:"

NO_HISTORY_TEXT = "Пока ничего не завершено и не отменено."
HISTORY_LIST_TEXT = "🗂 Последнее сделанное/отменённое:"

TASK_DONE_ANSWER = "Отмечено выполненным ✅"
TASK_CANCEL_ANSWER = "Задача отменена 🗑"
TASK_RECURRED_ANSWER = "Готово на этот раз 🔁 Задача вернётся к следующему сроку."
TASK_REOPEN_ANSWER = "Возвращено в работу 🔄"
NOT_ALLOWED_DONE = "Отметить задачу выполненной может только исполнитель или владелец."
NOT_ALLOWED_CANCEL = "Отменить задачу может только владелец."

ROLE_NOT_SET_TEXT = "Обязанности для тебя в этом чате пока не назначены."
SETROLE_NEEDS_REPLY_TEXT = (
    "Ответь этой командой на сообщение того админа, кому назначаешь обязанности: "
    "<code>/setrole текст обязанностей</code>."
)
SETROLE_USAGE_TEXT = "Напиши текст обязанностей после команды: <code>/setrole текст обязанностей</code>."
NOT_ALLOWED_SETROLE = "Назначать обязанности может только владелец чата."


def mention(tg_id: int, name: str) -> str:
    safe_name = name.replace("<", "").replace(">", "") or "пользователь"
    return f'<a href="tg://user?id={tg_id}">{safe_name}</a>'


def offer_admin_chat_prompt(bot_username: str) -> str:
    return (
        f"Добавь меня (@{bot_username}) в чат с админами, где ты хочешь ставить задачи — "
        "как только это произойдёт, я подключу его автоматически."
    )


def admin_chat_menu_text(title: str | None) -> str:
    label = title or "чат"
    return f"🗂 <b>{label}</b>\n\nЧто делаем?"


def task_card_text(task: Task) -> str:
    icon = "📦 Заказ" if task.kind == "order" else "📌 Задача"
    lines = [f"{icon} для {mention(task.assignee_tg_id, task.assignee_name or 'админа')}"]
    if task.kind == "order" and task.created_by_name:
        lines.append(f"от {task.created_by_name}")
    lines[0] = f"<b>{lines[0]}</b>"
    lines.append("")
    lines.append(task.title)
    lines.append("")
    if task.deadline:
        lines.append(f"⏳ Дедлайн: {format_deadline(task.deadline)}")
        if task.reminder_policy != "none":
            lines.append(f"🔔 {REMINDER_LABELS.get(task.reminder_policy, REMINDER_LABELS['none'])}")
        if task.recurrence != "none":
            lines.append(RECURRENCE_LABELS.get(task.recurrence, ""))
    else:
        lines.append("⏳ Без дедлайна")
    return "\n".join(lines)


def task_done_suffix() -> str:
    return "\n\n✅ <b>Выполнено</b>"


def task_cancelled_suffix() -> str:
    return "\n\n🗑 <b>Отменено</b>"


def pre_reminder_text(task: Task) -> str:
    return (
        f"⏰ Напоминание {mention(task.assignee_tg_id, task.assignee_name or 'админ')}: "
        f"дедлайн задачи «{task.title}» — {format_deadline(task.deadline)}."
    )


def deadline_reached_text(task: Task) -> str:
    return (
        f"🔥 {mention(task.assignee_tg_id, task.assignee_name or 'админ')}, дедлайн задачи "
        f"«{task.title}» наступил, а она ещё не выполнена."
    )


def overdue_nag_text(task: Task) -> str:
    return (
        f"🔁 {mention(task.assignee_tg_id, task.assignee_name or 'админ')}, задача «{task.title}» "
        f"всё ещё не выполнена (дедлайн был {format_deadline(task.deadline)})."
    )


def open_task_list_item(task: Task) -> str:
    deadline = format_deadline(task.deadline) if task.deadline else "без дедлайна"
    icon = "📦" if task.kind == "order" else "📌"
    return f"{icon} {task.title} — {task.assignee_name or 'админ'} ({deadline})"


def history_list_item(task: Task) -> str:
    icon = "✅" if task.status == "done" else "🗑"
    when = format_deadline(task.completed_at) if task.completed_at else ""
    return f"{icon} {task.title} — {task.assignee_name or 'админ'} ({when})"


def role_text(description: str | None) -> str:
    if not description:
        return ROLE_NOT_SET_TEXT
    return f"🗒 <b>Твои обязанности:</b>\n\n{description}"


def role_set_answer(target_name: str) -> str:
    return f"✅ Обязанности для {target_name} обновлены."
