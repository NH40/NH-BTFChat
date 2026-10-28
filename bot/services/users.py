"""Пользователи Telegram: запоминаем всех, кого видели, и ищем по @username / id."""
from __future__ import annotations

from aiogram.types import User as AiogramUser
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import TgUser, utcnow


async def upsert(session: AsyncSession, user: AiogramUser) -> None:
    """Запомнить/обновить пользователя (НЕ коммитит)."""
    if user.is_bot:
        return
    stmt = pg_insert(TgUser).values(
        id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name, last_seen_at=utcnow()
    )
    await session.execute(stmt.on_conflict_do_update(
        index_elements=[TgUser.id],
        set_={"username": stmt.excluded.username, "first_name": stmt.excluded.first_name,
              "last_name": stmt.excluded.last_name, "last_seen_at": stmt.excluded.last_seen_at},
    ))


async def ensure(session: AsyncSession, user_id: int) -> TgUser:
    """Строка пользователя по id (создаёт пустую, если бот его ещё не видел). НЕ коммитит."""
    row = await session.get(TgUser, user_id)
    if row is None:
        row = TgUser(id=user_id)
        session.add(row)
        await session.flush()
    return row


async def resolve(session: AsyncSession, ref: str) -> TgUser | None:
    """«123456», «@nick» или «nick» → пользователь, которого бот видел."""
    ref = (ref or "").strip().lstrip("@")
    if not ref:
        return None
    if ref.lstrip("-").isdigit():
        return await session.get(TgUser, int(ref))
    return await session.scalar(select(TgUser).where(func.lower(TgUser.username) == ref.lower()).limit(1))


async def get_many(session: AsyncSession, ids: set[int] | list[int]) -> dict[int, TgUser]:
    if not ids:
        return {}
    rows = await session.scalars(select(TgUser).where(TgUser.id.in_(list(ids))))
    return {u.id: u for u in rows}
