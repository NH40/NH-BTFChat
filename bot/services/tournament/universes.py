from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db import Character, Universe


async def create_universe(session: AsyncSession, *, name: str, created_by_tg_id: int) -> Universe:
    universe = Universe(name=name, created_by_tg_id=created_by_tg_id)
    universe.characters = []
    session.add(universe)
    await session.commit()
    return universe


async def get_universe_by_name(session: AsyncSession, name: str) -> Universe | None:
    result = await session.execute(select(Universe).where(Universe.name.ilike(name)))
    return result.scalar_one_or_none()


async def list_universes(session: AsyncSession) -> list[Universe]:
    result = await session.execute(select(Universe).order_by(Universe.name))
    return list(result.scalars().all())


async def get_universe_with_characters(session: AsyncSession, universe_id: int) -> Universe | None:
    result = await session.execute(
        select(Universe).options(selectinload(Universe.characters)).where(Universe.id == universe_id)
    )
    return result.scalar_one_or_none()


async def add_character(
    session: AsyncSession, *, universe_id: int, name: str, note: str | None = None
) -> Character:
    character = Character(universe_id=universe_id, name=name, note=note)
    session.add(character)
    await session.commit()
    return character


async def remove_character(session: AsyncSession, character_id: int) -> None:
    character = await session.get(Character, character_id)
    if character:
        await session.delete(character)
        await session.commit()


async def get_character(session: AsyncSession, character_id: int) -> Character | None:
    return await session.get(Character, character_id)


async def list_characters(session: AsyncSession, universe_id: int) -> list[Character]:
    result = await session.execute(
        select(Character).where(Character.universe_id == universe_id).order_by(Character.name)
    )
    return list(result.scalars().all())
