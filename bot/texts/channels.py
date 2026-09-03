ADD_CHANNEL_PROMPT = "Пришли @username канала (или ссылку на него), который нужно подключить."
ADD_CHANNEL_CANCELLED = "Добавление канала отменено."
PENDING_CANCELLED = "Действие отменено."

INVITE_LINK_ERROR = (
    "Это приватная пригласительная ссылка. Я умею подключать только публичные каналы "
    "с @username. Пришли @username канала или ссылку вида https://t.me/username."
)
UNKNOWN_FORMAT_ERROR = "Не понял формат. Пришли @username канала или ссылку вида https://t.me/username."
CHANNEL_NOT_FOUND_ERROR = "Не могу найти такой канал. Проверь юзернейм и убедись, что канал публичный."
NOT_A_CHANNEL_ERROR = "Это не канал. Пришли юзернейм именно канала."

PICK_CHAT_SUCCESS = "✅ Готово! Посты из этого канала будут пересылаться в выбранный чат."

NO_SUBS_TEXT = "Пока нет ни одного правила пересылки."
SUBS_LIST_TEXT = "Твои правила пересылки:"
SUB_DELETED_ANSWER = "Правило удалено."


def admin_rights_prompt(bot_username: str, channel_title: str) -> str:
    return (
        f"Добавь меня (@{bot_username}) администратором в канал «{channel_title}» "
        "с правом публикации сообщений — как только это произойдёт, я подключу канал автоматически."
    )


def offer_target_chat_prompt(channel_title: str) -> str:
    return f"Канал «{channel_title}» подключён. Куда пересылать посты?"


def new_chat_prompt(bot_username: str) -> str:
    return (
        f"Добавь меня (@{bot_username}) в чат или группу, куда нужно пересылать посты — "
        "как только это произойдёт, я подключу его автоматически."
    )
