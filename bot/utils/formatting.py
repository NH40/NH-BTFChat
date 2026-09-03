from __future__ import annotations

from bot.db import Channel


def build_signature(channel: Channel) -> str:
    label = channel.title or (f"@{channel.username}" if channel.username else "канал")
    if channel.username:
        return f'\n\n📡 <a href="https://t.me/{channel.username}">{label}</a>'
    return f"\n\n📡 {label}"


def append_signature(text: str | None, signature: str, limit: int) -> str:
    body = text or ""
    combined = body + signature
    if len(combined) <= limit:
        return combined
    allowed_body = max(limit - len(signature), 0)
    return body[:allowed_body] + signature
