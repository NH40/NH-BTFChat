from __future__ import annotations

import datetime as dt

# Bot audience runs on Moscow time; storage stays UTC (utcnow(), like the rest of the app).
MSK_OFFSET = dt.timedelta(hours=3)

_DEADLINE_INPUT_FORMATS = ("%d.%m.%Y %H:%M", "%d.%m.%Y")


def parse_deadline_input(text: str) -> dt.datetime | None:
    text = text.strip()
    for fmt in _DEADLINE_INPUT_FORMATS:
        try:
            local = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        return local - MSK_OFFSET
    return None


def format_deadline(deadline: dt.datetime) -> str:
    local = deadline + MSK_OFFSET
    return local.strftime("%d.%m.%Y %H:%M") + " МСК"
