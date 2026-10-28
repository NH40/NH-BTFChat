"""Пересылка из каналов: связки канал → чаты, проверка удалений, последние посты. Только старшие."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, bad, get_session, not_found, senior
from api.serializers import chat_out, iso
from bot.db import Chat, RelayCopy, RelayPost, RelayRoute
from bot.db.models.chats import KIND_CHANNEL, KIND_SERVICE
from bot.services import app_settings

router = APIRouter(prefix="/api/relay", tags=["relay"])


@router.get("")
async def overview(v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    chats = list(await session.scalars(select(Chat).where(Chat.bot_status != "left").order_by(Chat.title)))
    routes = list(await session.scalars(select(RelayRoute).where(RelayRoute.active.is_(True))))
    posts = dict((await session.execute(
        select(RelayPost.channel_id, func.count()).where(RelayPost.deleted.is_(False)).group_by(RelayPost.channel_id))).all())
    service = (await app_settings.get(session, app_settings.KEY_SERVICE_CHAT)).get("chat_id")
    return {
        "channels": [{**chat_out(c), "posts": posts.get(c.id, 0),
                      "targets": [r.target_chat_id for r in routes if r.channel_id == c.id]}
                     for c in chats if c.type == "channel"],
        "targets": [chat_out(c) for c in chats if c.type != "channel" and c.kind != KIND_SERVICE],
        "service_chat": next((chat_out(c) for c in chats if c.id == service), None),
        "check": await app_settings.get(session, app_settings.KEY_RELAY_CHECK),
    }


class RoutesIn(BaseModel):
    target_ids: list[int]


@router.put("/channels/{channel_id}")
async def set_routes(channel_id: int, body: RoutesIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    """Куда пересылать канал — полный список чатов (заменяет прежний)."""
    channel = await session.get(Chat, channel_id)
    if channel is None or channel.type != "channel":
        raise not_found("Канал не найден — добавьте бота админом канала")
    targets = {c.id: c for c in await session.scalars(select(Chat).where(Chat.id.in_(body.target_ids)))} if body.target_ids else {}
    if any(c.type == "channel" or c.kind == KIND_SERVICE for c in targets.values()) or len(targets) != len(set(body.target_ids)):
        raise bad("Пересылать можно только в группы (не в каналы и не в служебный чат)")
    channel.kind = KIND_CHANNEL
    existing = {r.target_chat_id: r for r in await session.scalars(select(RelayRoute).where(RelayRoute.channel_id == channel_id))}
    for tid, route in existing.items():
        route.active = tid in targets
    for tid in targets.keys() - existing.keys():
        session.add(RelayRoute(channel_id=channel_id, target_chat_id=tid, active=True))
    await session.commit()
    return {"ok": True}


class CheckIn(BaseModel):
    enabled: bool = True
    window_hours: int = Field(48, ge=1, le=24 * 14)
    interval_minutes: int = Field(30, ge=5, le=24 * 60)
    batch: int = Field(15, ge=1, le=100)


@router.put("/check")
async def set_check(body: CheckIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    await app_settings.put(session, app_settings.KEY_RELAY_CHECK, body.model_dump())
    await session.commit()
    return {"ok": True}


@router.get("/posts")
async def recent_posts(channel_id: int | None = None, limit: int = 30, v: Viewer = Depends(senior),
                       session: AsyncSession = Depends(get_session)):
    q = select(RelayPost).order_by(RelayPost.created_at.desc()).limit(min(limit, 100))
    if channel_id:
        q = q.where(RelayPost.channel_id == channel_id)
    posts = list(await session.scalars(q))
    copies = dict((await session.execute(
        select(RelayCopy.post_id, func.count()).where(RelayCopy.post_id.in_([p.id for p in posts])).group_by(RelayCopy.post_id))).all()) if posts else {}
    titles = dict((await session.execute(select(Chat.id, Chat.title).where(Chat.id.in_({p.channel_id for p in posts})))).all()) if posts else {}
    return [{"id": p.id, "channel_id": p.channel_id, "channel": titles.get(p.channel_id), "message_id": p.message_id,
             "parts": len(p.message_ids or []), "version": p.version, "deleted": p.deleted, "copies": copies.get(p.id, 0),
             "created_at": iso(p.created_at), "last_checked_at": iso(p.last_checked_at)} for p in posts]
