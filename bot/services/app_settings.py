"""Общие настройки приложения (таблица app_settings) со значениями по умолчанию."""
from __future__ import annotations

import copy

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import AppSetting

KEY_ADMIN_CHAT = "admin_chat"  # {"chat_id": int|None} — чат админов для напоминаний
KEY_SERVICE_CHAT = "service_chat"  # {"chat_id": int|None} — служебный чат для проверки постов
KEY_RELAY_CHECK = "relay_check"  # проверка удаления постов каналов
KEY_REMINDER_DEFAULTS = "reminder_defaults"  # напоминания, которые ставятся новой задаче с дедлайном

DEFAULTS: dict[str, dict] = {
    KEY_ADMIN_CHAT: {"chat_id": None},
    KEY_SERVICE_CHAT: {"chat_id": None},
    # Посты моложе `window_hours` проверяются раз в `interval_minutes`, не больше `batch` за проход.
    KEY_RELAY_CHECK: {"enabled": True, "window_hours": 48, "interval_minutes": 30, "batch": 15},
    KEY_REMINDER_DEFAULTS: {"items": [
        {"kind": "before", "offset_minutes": 60},
        {"kind": "overdue", "interval_minutes": 180},
    ]},
}


async def get(session: AsyncSession, key: str) -> dict:
    row = await session.get(AppSetting, key)
    value = copy.deepcopy(DEFAULTS.get(key, {}))
    if row is not None and isinstance(row.value, dict):
        value.update(row.value)
    return value


async def put(session: AsyncSession, key: str, value: dict) -> None:
    """Записать (НЕ коммитит)."""
    stmt = pg_insert(AppSetting).values(key=key, value=value)
    await session.execute(stmt.on_conflict_do_update(index_elements=[AppSetting.key], set_={"value": stmt.excluded.value}))
