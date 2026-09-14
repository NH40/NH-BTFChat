from __future__ import annotations

from html import escape

from bot.constant import RECURRENCE_LABELS, REMINDER_LABELS
from bot.db import Task
from bot.utils.time import format_deadline, relative_label

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
OPEN_TASKS_LIST_TEXT = "📋 Открытые задачи (нажми, чтобы открыть и отметить):"

NO_OPEN_ORDERS_TEXT = "Открытых заказов пока нет."
OPEN_ORDERS_LIST_TEXT = "📦 Очередь заказов (нажми, чтобы открыть и отметить):"

NO_MY_TASKS_TEXT = "На тебе сейчас нет открытых задач."
MY_TASKS_LIST_TEXT = "🙋 Твои открытые задачи (нажми, чтобы открыть и отметить):"

NO_HISTORY_TEXT = "Пока ничего не завершено и не отменено."
HISTORY_LIST_TEXT = "🗂 Последнее сделанное/отменённое:"

TASK_DONE_ANSWER = "Отмечено выполненным ✅"
TASK_MISSED_ANSWER = "Отмечено как не выполненное ❌"
TASK_CANCEL_ANSWER = "Задача отменена 🗑"
TASK_RECURRED_ANSWER = "Готово на этот раз 🔁 Задача вернётся к следующему сроку."
TASK_REOPEN_ANSWER = "Возвращено в работу 🔄"
NOT_ALLOWED_DONE = "Отметить статус задачи может только исполнитель или владелец."
NOT_ALLOWED_CANCEL = "Отменить задачу может только владелец."

ROLE_NOT_SET_TEXT = "Обязанности для тебя в этом чате пока не назначены."
SETROLE_NEEDS_REPLY_TEXT = (
    "Ответь этой командой на сообщение того админа, кому назначаешь обязанности: "
    "<code>/setrole текст обязанностей</code>."
)
SETROLE_USAGE_TEXT = "Напиши текст обязанностей после команды: <code>/setrole текст обязанностей</code>."
NOT_ALLOWED_SETROLE = "Назначать обязанности может только владелец чата."

NOT_ALLOWED_STATS = "Смотреть статистику может только владелец чата."
NO_STATS_TEXT = "Пока нет данных для статистики — ни одна задача ещё не была отмечена выполненной или невыполненной."
STATS_TITLE = "📊 <b>Статистика по задачам</b>"


def mention(tg_id: int, name: str) -> str:
    safe_name = escape(name, quote=False) or "пользователь"
    return f'<a href="tg://user?id={tg_id}">{safe_name}</a>'


def offer_admin_chat_prompt(bot_username: str) -> str:
    return (
        f"Добавь меня (@{bot_username}) в чат с админами, где ты хочешь ставить задачи — "
        "как только это произойдёт, я подключу его автоматически."
    )


def admin_chat_menu_text(title: str | None) -> str:
    label = title or "чат"
    return f"🗂 <b>{label}</b>\n\nЧто делаем?"


def _kind_icon(task: Task) -> str:
    if task.recurrence != "none":
        return "🔁"
    return "📦" if task.kind == "order" else "📌"


def _deadline_block(task: Task, *, prefix: str = "⏳ Дедлайн: ") -> str:
    if not task.deadline:
        return "⏳ Без дедлайна"
    return f"{prefix}{format_deadline(task.deadline)} · {relative_label(task.deadline)}"


def _status_line(task: Task) -> str:
    if task.status == "open":
        return "Статус: 🟡 в работе"
    if task.status == "done":
        if task.deadline and task.completed_at:
            on_time = task.completed_at <= task.deadline
            return "Статус: ✅ выполнено вовремя" if on_time else "Статус: ✅ выполнено (с опозданием)"
        return "Статус: ✅ выполнено"
    if task.status == "missed":
        return "Статус: ❌ не выполнено"
    if task.status == "cancelled":
        return "Статус: 🗑 отменено"
    return f"Статус: {task.status}"


def task_card_text(task: Task) -> str:
    icon = "📦 Заказ" if task.kind == "order" else "📌 Задача"
    lines = [f"{icon} для {mention(task.assignee_tg_id, task.assignee_name or 'админа')}"]
    if task.kind == "order" and task.created_by_name:
        lines.append(f"от {task.created_by_name}")
    lines[0] = f"<b>{lines[0]}</b>"
    lines.append("")
    lines.append(escape(task.title, quote=False))
    lines.append("")
    lines.append(_deadline_block(task))
    if task.deadline:
        if task.reminder_policy != "none":
            lines.append(f"🔔 {REMINDER_LABELS.get(task.reminder_policy, REMINDER_LABELS['none'])}")
        if task.recurrence != "none":
            lines.append(RECURRENCE_LABELS.get(task.recurrence, ""))
    lines.append("")
    lines.append(_status_line(task))
    return "\n".join(lines)


def pre_reminder_text(task: Task) -> str:
    return (
        f"⏰ Напоминание {mention(task.assignee_tg_id, task.assignee_name or 'админ')}: "
        f"дедлайн задачи «{escape(task.title, quote=False)}» — {format_deadline(task.deadline)}."
    )


def deadline_reached_text(task: Task) -> str:
    return (
        f"🔥 {mention(task.assignee_tg_id, task.assignee_name or 'админ')}, дедлайн задачи "
        f"«{escape(task.title, quote=False)}» наступил, а она ещё не выполнена."
    )


def overdue_nag_text(task: Task) -> str:
    return (
        f"🔁 {mention(task.assignee_tg_id, task.assignee_name or 'админ')}, задача "
        f"«{escape(task.title, quote=False)}» всё ещё не выполнена "
        f"(дедлайн был {format_deadline(task.deadline)})."
    )


def open_task_list_item(index: int, task: Task) -> str:
    """Full board view (/alltasks, /orders): shows who it's for/from."""
    icon = _kind_icon(task)
    title = escape(task.title, quote=False)
    if task.kind == "order":
        who = f"от {task.created_by_name or '?'} → {task.assignee_name or 'админ'}"
    else:
        who = task.assignee_name or "админ"
    return f"{index}. {icon} <b>{title}</b> — {who}\n    {_deadline_block(task, prefix='')}"


def my_task_list_item(index: int, task: Task) -> str:
    """Personal view (/tasks, /mytasks): the assignee is always the reader, so skip it."""
    icon = _kind_icon(task)
    title = escape(task.title, quote=False)
    return f"{index}. {icon} <b>{title}</b>\n    {_deadline_block(task, prefix='')}"


def history_list_item(index: int, task: Task) -> str:
    icon = {"done": "✅", "missed": "❌", "cancelled": "🗑"}.get(task.status, "•")
    when = f" · {format_deadline(task.completed_at)}" if task.completed_at else ""
    title = escape(task.title, quote=False)
    return f"{index}. {icon} {title} — {task.assignee_name or 'админ'}{when}"


def role_text(description: str | None) -> str:
    if not description:
        return ROLE_NOT_SET_TEXT
    return f"🗒 <b>Твои обязанности:</b>\n\n{escape(description, quote=False)}"


def role_set_answer(target_name: str) -> str:
    return f"✅ Обязанности для {target_name} обновлены."


def stats_text(rows: list[dict]) -> str:
    if not rows:
        return NO_STATS_TEXT
    lines = [STATS_TITLE, ""]
    for index, row in enumerate(rows, start=1):
        rate = f"{row['on_time']}/{row['done']}" if row["done"] else "0/0"
        name = escape(row["name"] or "админ", quote=False)
        lines.append(f"{index}. {name} — ✅ {row['done']} (вовремя {rate}), ❌ {row['missed']}")
    return "\n".join(lines)
