"""Зависимости API: авторизация по initData Telegram, сессия БД, роль в команде, Bot."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import parse_qsl

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db import TgUser, session_factory, utcnow
from bot.db.models.users import ROLE_ADMIN, ROLE_OWNER, ROLE_SENIOR
from bot.services import staff

INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60
_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bot


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


def _validate(init_data: str) -> dict:
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Некорректный initData") from exc
    received = pairs.pop("hash", None)
    if not received:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нет подписи initData")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), received):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверная подпись initData")
    if time.time() - int(pairs.get("auth_date", "0") or 0) > INIT_DATA_MAX_AGE_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData устарел — переоткройте Mini App")
    try:
        return json.loads(pairs["user"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нет пользователя в initData") from exc


@dataclass
class Viewer:
    id: int
    role: str

    @property
    def is_owner(self) -> bool:
        return self.role == ROLE_OWNER

    @property
    def is_senior(self) -> bool:
        return staff.at_least(self.role, ROLE_SENIOR)


async def viewer(x_telegram_init_data: str = Header(alias="X-Telegram-Init-Data"),
                 session: AsyncSession = Depends(get_session)) -> Viewer:
    user = _validate(x_telegram_init_data)
    uid = int(user["id"])
    stmt = pg_insert(TgUser).values(id=uid, username=user.get("username"), first_name=user.get("first_name"),
                                    last_name=user.get("last_name"), last_seen_at=utcnow())
    await session.execute(stmt.on_conflict_do_update(index_elements=[TgUser.id], set_={
        "username": stmt.excluded.username, "first_name": stmt.excluded.first_name,
        "last_name": stmt.excluded.last_name, "last_seen_at": stmt.excluded.last_seen_at}))
    await session.commit()
    role = await staff.role_of(session, uid)
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступ только для команды BTF")
    return Viewer(uid, role)


async def senior(v: Viewer = Depends(viewer)) -> Viewer:
    if not v.is_senior:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нужна роль «старший» или выше")
    return v


async def owner(v: Viewer = Depends(viewer)) -> Viewer:
    if not v.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Только для владельца")
    return v


def bad(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, msg)


def not_found(msg: str = "Не найдено") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, msg)


__all__ = ["ROLE_ADMIN", "Viewer", "bad", "get_bot", "get_session", "not_found", "owner", "senior", "viewer"]
