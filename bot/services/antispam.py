"""Антиспам: флуд, ссылки, запрещённые слова, чужие пересылки. Решает, что нарушено и что делать."""
from __future__ import annotations

import re
from dataclasses import dataclass

from aiogram.types import Message

from bot.redis import redis

_URL_RE = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/)\S+|\b[\w-]+\.(ru|com|net|org|io|me|gg|xyz|su|рф)\b", re.IGNORECASE)


@dataclass
class Violation:
    kind: str  # flood / link / word / forward
    action: str  # delete / warn / mute / ban
    mute_minutes: int
    reason: str


def _text(msg: Message) -> str:
    return (msg.text or msg.caption or "")


def _links(msg: Message) -> list[str]:
    found: list[str] = []
    text = _text(msg)
    for ent in (msg.entities or []) + (msg.caption_entities or []):
        if ent.type == "text_link" and ent.url:
            found.append(ent.url)
        elif ent.type == "url":
            found.append(text[ent.offset:ent.offset + ent.length])
    found += [m.group(0) for m in _URL_RE.finditer(text)]
    return found


def _whitelisted(link: str, whitelist: list[str]) -> bool:
    link = link.lower()
    return any(w and w.lower() in link for w in whitelist)


async def check(msg: Message, cfg: dict) -> Violation | None:
    """Первое найденное нарушение по настройкам чата (`moderation_settings.merged`)."""
    flood = cfg["antiflood"]
    if flood["enabled"] and msg.from_user:
        key = f"flood:{msg.chat.id}:{msg.from_user.id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, int(flood["seconds"]))
        if count > int(flood["messages"]):
            return Violation("flood", flood["action"], flood["mute_minutes"],
                             f"флуд: больше {flood['messages']} сообщений за {flood['seconds']} с")

    words = cfg["words"]
    if words["enabled"] and words["list"]:
        low = _text(msg).lower()
        for w in words["list"]:
            if w and w.lower() in low:
                return Violation("word", words["action"], words["mute_minutes"], "запрещённое слово")

    links = cfg["links"]
    if links["enabled"]:
        bad = [x for x in _links(msg) if not _whitelisted(x, links["whitelist"])]
        if bad:
            return Violation("link", links["action"], links["mute_minutes"], "ссылка")

    fwd = cfg["forwards"]
    if fwd["enabled"] and msg.forward_origin is not None:
        return Violation("forward", fwd["action"], fwd["mute_minutes"], "пересылка из стороннего источника")
    return None
