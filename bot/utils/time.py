"""Время: «сейчас», разбор длительностей (30m / 2h / 1d / 1w) и вывод в часовом поясе команды."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from bot.config import settings

_DURATION_RE = re.compile(r"^(\d+)\s*(s|m|h|d|w|с|м|мин|ч|д|н)?$", re.IGNORECASE)
_UNITS = {
    "s": 1, "с": 1,
    "m": 60, "м": 60, "мин": 60,
    "h": 3600, "ч": 3600,
    "d": 86400, "д": 86400,
    "w": 604800, "н": 604800,
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_duration(raw: str | None) -> timedelta | None:
    """«30m», «2h», «1d», «45» (минуты), «2ч». None — не длительность."""
    if not raw:
        return None
    m = _DURATION_RE.match(raw.strip())
    if not m:
        return None
    value = int(m.group(1))
    unit = (m.group(2) or "m").lower()
    seconds = value * _UNITS[unit]
    return timedelta(seconds=seconds) if seconds > 0 else None


def human_duration(td: timedelta | None) -> str:
    if td is None:
        return "навсегда"
    s = int(td.total_seconds())
    for size, name in ((604800, "нед"), (86400, "д"), (3600, "ч"), (60, "мин")):
        if s >= size and s % size == 0:
            return f"{s // size} {name}"
    if s >= 3600:
        return f"{s // 3600} ч {s % 3600 // 60} мин"
    return f"{max(1, s // 60)} мин"


def local(dt: datetime | None) -> datetime | None:
    return dt.astimezone(settings.tz) if dt else None


def fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    loc = local(dt)
    today = now().astimezone(settings.tz).date()
    if loc.date() == today:
        return f"сегодня {loc:%H:%M}"
    if (loc.date() - today).days == 1:
        return f"завтра {loc:%H:%M}"
    return f"{loc:%d.%m %H:%M}"
