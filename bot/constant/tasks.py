import datetime as dt

# Task planner (admin chats)
MAX_TASK_TITLE_LENGTH = 1024

DEADLINE_PRESETS: dict[str, dt.timedelta] = {
    "1d": dt.timedelta(days=1),
    "3d": dt.timedelta(days=3),
    "1w": dt.timedelta(weeks=1),
}
DEADLINE_PRESET_LABELS: dict[str, str] = {
    "1d": "Завтра",
    "3d": "Через 3 дня",
    "1w": "Через неделю",
}

REMINDER_POLICIES = ("none", "before_1h", "before_1d", "daily_until_done")
REMINDER_LABELS: dict[str, str] = {
    "none": "Без напоминаний",
    "before_1h": "⏰ За 1 час до дедлайна",
    "before_1d": "⏰ За 1 день до дедлайна",
    "daily_until_done": "🔁 Каждый день, пока не выполнено",
}

TASK_REMINDER_POLL_SECONDS = 10 * 60
TASK_REMINDER_NAG_INTERVAL = dt.timedelta(hours=24)
