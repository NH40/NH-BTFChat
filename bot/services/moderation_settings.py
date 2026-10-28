"""Настройки модерации чата: значения по умолчанию и слияние с сохранёнными (chats.settings)."""
from __future__ import annotations

import copy

# Действие при нарушении: delete — удалить сообщение; warn — удалить + предупреждение;
# mute — удалить + мут на mute_minutes; ban — удалить + бан.
ACTIONS = ("delete", "warn", "mute", "ban")

DEFAULTS: dict = {
    "enabled": True,
    # Команды /ban /mute ... доступны админам чата Telegram (с правом ограничивать) и
    # старшим/владельцам команды BTF.
    "chat_admins_can_moderate": True,
    "ignore_staff": True,  # антиспам не трогает админов чата и команду
    "warns": {"limit": 3, "action": "mute", "mute_minutes": 1440, "expire_days": 30},
    "antiflood": {"enabled": True, "messages": 6, "seconds": 10, "action": "mute", "mute_minutes": 30},
    "links": {"enabled": False, "action": "delete", "mute_minutes": 30, "whitelist": []},
    "words": {"enabled": False, "action": "delete", "mute_minutes": 30, "list": []},
    "forwards": {"enabled": False, "action": "delete", "mute_minutes": 30},  # пересылки из чужих каналов
    "welcome": {"enabled": False, "text": "Добро пожаловать, {name}! Правила — /rules", "delete_after_seconds": 0},
    "rules": "",
    "log_actions": True,  # писать в чат о действиях модерации
}


def merged(saved: dict | None) -> dict:
    """Сохранённые настройки поверх значений по умолчанию (на любую глубину вложенности)."""
    result = copy.deepcopy(DEFAULTS)

    def apply(dst: dict, src: dict) -> None:
        for key, value in (src or {}).items():
            if isinstance(value, dict) and isinstance(dst.get(key), dict):
                apply(dst[key], value)
            elif key in dst:
                dst[key] = value

    apply(result, saved or {})
    return result
