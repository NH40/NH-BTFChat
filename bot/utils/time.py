from __future__ import annotations

import datetime as dt

# Bot audience runs on Moscow time; storage stays UTC (utcnow(), like the rest of the app).
MSK_OFFSET = dt.timedelta(hours=3)

_DEADLINE_INPUT_FORMATS_WITH_YEAR = ("%d.%m.%Y %H:%M", "%d.%m.%Y")
_DEADLINE_INPUT_FORMATS_NO_YEAR = ("%d.%m %H:%M", "%d.%m")


def parse_deadline_input(text: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """Accepts ДД.ММ.ГГГГ [ЧЧ:ММ] or the shorthand ДД.ММ [ЧЧ:ММ] (assumes the current
    Moscow year, rolling to next year if that date has already passed)."""
    text = text.strip()
    now = now or dt.datetime.utcnow()

    for fmt in _DEADLINE_INPUT_FORMATS_WITH_YEAR:
        try:
            local = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        return local - MSK_OFFSET

    local_now = now + MSK_OFFSET
    for fmt in _DEADLINE_INPUT_FORMATS_NO_YEAR:
        try:
            local = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        try:
            local = local.replace(year=local_now.year)
        except ValueError:
            local = local.replace(year=local_now.year, day=28)  # Feb 29 on a non-leap year
        if local < local_now:
            try:
                local = local.replace(year=local_now.year + 1)
            except ValueError:
                local = local.replace(year=local_now.year + 1, day=28)
        return local - MSK_OFFSET

    return None


def format_deadline(deadline: dt.datetime) -> str:
    local = deadline + MSK_OFFSET
    return local.strftime("%d.%m.%Y %H:%M") + " МСК"


def relative_label(moment: dt.datetime, now: dt.datetime | None = None) -> str:
    """Short relative offset like 'через 3 ч' / 'просрочено на 2 дн'."""
    now = now or dt.datetime.utcnow()
    total_minutes = int((moment - now).total_seconds() // 60)
    overdue = total_minutes < 0
    minutes = abs(total_minutes)

    if minutes < 60:
        value, unit = minutes, "мин"
    elif minutes < 60 * 24:
        value, unit = minutes // 60, "ч"
    else:
        value, unit = minutes // (60 * 24), "дн"

    if value == 0:
        return "прямо сейчас"
    return f"просрочено на {value} {unit}" if overdue else f"через {value} {unit}"
