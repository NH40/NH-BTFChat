"""HTML-экранирование и упоминания людей."""
from __future__ import annotations

from html import escape


def esc(value: object) -> str:
    return escape(str(value), quote=False)


def mention(user_id: int, username: str | None = None, name: str | None = None) -> str:
    """@username, если есть (пингует в чате), иначе кликабельное имя по id (тоже пингует)."""
    if username:
        return f"@{esc(username)}"
    return f'<a href="tg://user?id={user_id}">{esc(name or user_id)}</a>'
