"""Чаты и модерация: назначение чатов, настройки модерации чата, журнал, предупреждения,
действия из панели. Только старшие и владелец."""
from __future__ import annotations

from datetime import timedelta

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, bad, get_bot, get_session, not_found, senior
from api.serializers import chat_out, iso, user_out
from bot.db import Chat, ChatWarning, ModAction, RelayRoute
from bot.db.models.chats import KIND_ADMIN, KIND_CHANNEL, KIND_NONE, KIND_SERVICE, KINDS
from bot.services import app_settings, moderation, users
from bot.services.moderation_settings import ACTIONS, merged
from bot.utils.text import esc, mention
from bot.utils.time import now

router = APIRouter(prefix="/api/chats", tags=["chats"])

_SINGLE_KINDS = {KIND_ADMIN: app_settings.KEY_ADMIN_CHAT, KIND_SERVICE: app_settings.KEY_SERVICE_CHAT}


async def _chat(session: AsyncSession, chat_id: int) -> Chat:
    chat = await session.get(Chat, chat_id)
    if chat is None:
        raise not_found("Чат не найден — добавьте в него бота")
    return chat


@router.get("")
async def list_chats(v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    chats = list(await session.scalars(select(Chat).order_by(Chat.kind, Chat.title)))
    as_source = dict((await session.execute(
        select(RelayRoute.channel_id, func.count()).where(RelayRoute.active.is_(True)).group_by(RelayRoute.channel_id))).all())
    as_target = dict((await session.execute(
        select(RelayRoute.target_chat_id, func.count()).where(RelayRoute.active.is_(True)).group_by(RelayRoute.target_chat_id))).all())
    return [{**chat_out(c), "routes_out": as_source.get(c.id, 0), "routes_in": as_target.get(c.id, 0)} for c in chats]


class KindIn(BaseModel):
    kind: str


@router.put("/{chat_id}/kind")
async def set_kind(chat_id: int, body: KindIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    """Назначение чата. Чат админов и служебный — по одному: прежний сбрасывается в «без назначения»."""
    if body.kind not in KINDS:
        raise bad("Неизвестное назначение")
    chat = await _chat(session, chat_id)
    if (chat.type == "channel") != (body.kind == KIND_CHANNEL) and body.kind != KIND_NONE:
        raise bad("Канал может быть только источником, а группа — не каналом")
    old_kind = chat.kind
    if body.kind in _SINGLE_KINDS:
        for other in await session.scalars(select(Chat).where(Chat.kind == body.kind, Chat.id != chat.id)):
            other.kind = KIND_NONE
        await app_settings.put(session, _SINGLE_KINDS[body.kind], {"chat_id": chat.id})
    if old_kind in _SINGLE_KINDS and old_kind != body.kind:
        await app_settings.put(session, _SINGLE_KINDS[old_kind], {"chat_id": None})
    chat.kind = body.kind
    await session.commit()
    return {"ok": True}


@router.delete("/{chat_id}")
async def forget_chat(chat_id: int, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    """Убрать чат из списка (если бот уже вышел). Бот в нём остаётся, если ещё там."""
    chat = await _chat(session, chat_id)
    if chat.kind in _SINGLE_KINDS:
        await app_settings.put(session, _SINGLE_KINDS[chat.kind], {"chat_id": None})
    await session.delete(chat)
    await session.commit()
    return {"ok": True}


@router.get("/{chat_id}/settings")
async def get_settings(chat_id: int, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    return {"chat": chat_out(chat), "settings": merged(chat.settings), "actions": list(ACTIONS)}


@router.put("/{chat_id}/settings")
async def put_settings(chat_id: int, body: dict, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    cfg = merged(body)  # неизвестные ключи отбрасываются, недостающие — по умолчанию
    for block in ("antiflood", "links", "words", "forwards"):
        if cfg[block]["action"] not in ACTIONS:
            raise bad(f"Неизвестное действие в «{block}»")
    if cfg["warns"]["action"] not in ("mute", "ban") or int(cfg["warns"]["limit"]) < 1:
        raise bad("Предупреждения: лимит ≥ 1, действие — мут или бан")
    chat.settings = cfg
    await session.commit()
    return {"ok": True}


@router.get("/{chat_id}/actions")
async def list_actions(chat_id: int, offset: int = 0, limit: int = 50, v: Viewer = Depends(senior),
                       session: AsyncSession = Depends(get_session)):
    rows = list(await session.scalars(select(ModAction).where(ModAction.chat_id == chat_id)
                                      .order_by(ModAction.created_at.desc()).offset(offset).limit(min(limit, 200))))
    people = await users.get_many(session, {r.target_id for r in rows} | {r.actor_id for r in rows if r.actor_id})
    return [{"id": r.id, "action": r.action, "reason": r.reason, "until": iso(r.until), "created_at": iso(r.created_at),
             "target": user_out(people.get(r.target_id), r.target_id),
             "actor": user_out(people.get(r.actor_id), r.actor_id) if r.actor_id else None} for r in rows]


@router.get("/{chat_id}/warnings")
async def list_warnings(chat_id: int, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    expire = merged(chat.settings)["warns"]["expire_days"]
    q = select(ChatWarning.user_id, func.count(), func.max(ChatWarning.created_at)).where(
        ChatWarning.chat_id == chat_id, ChatWarning.active.is_(True))
    if expire:
        q = q.where(ChatWarning.created_at >= now() - timedelta(days=expire))
    rows = (await session.execute(q.group_by(ChatWarning.user_id).order_by(func.count().desc()))).all()
    people = await users.get_many(session, {uid for uid, _, _ in rows})
    return [{"user": user_out(people.get(uid), uid), "count": count, "last_at": iso(last)} for uid, count, last in rows]


class ModerateIn(BaseModel):
    action: str  # ban / unban / mute / unmute / kick / warn / unwarn
    user: str = Field(min_length=1)  # id или @username
    minutes: int | None = None  # срок бана/мута; пусто — навсегда
    reason: str | None = Field(None, max_length=500)


@router.post("/{chat_id}/moderate")
async def moderate(chat_id: int, body: ModerateIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    target = await users.resolve(session, body.user)
    if target is None:
        if not body.user.strip().lstrip("-").isdigit():
            raise not_found("Пользователь не найден — укажите числовой id")
        target = await users.ensure(session, int(body.user.strip()))
    bot = get_bot()
    duration = timedelta(minutes=body.minutes) if body.minutes else None
    try:
        if body.action == "ban":
            await moderation.ban(bot, session, chat.id, target.id, v.id, duration, body.reason)
        elif body.action == "unban":
            await moderation.unban(bot, session, chat.id, target.id, v.id)
        elif body.action == "mute":
            await moderation.mute(bot, session, chat.id, target.id, v.id, duration, body.reason)
        elif body.action == "unmute":
            await moderation.unmute(bot, session, chat.id, target.id, v.id)
        elif body.action == "kick":
            await moderation.kick(bot, session, chat.id, target.id, v.id, body.reason)
        elif body.action == "warn":
            await moderation.warn(bot, session, chat, target.id, v.id, body.reason)
        elif body.action == "unwarn":
            await moderation.unwarn(session, chat.id, target.id, v.id)
        else:
            raise bad("Неизвестное действие")
    except moderation.ModerationError as exc:
        raise bad(f"Telegram отказал: {exc}") from exc
    await session.commit()
    if merged(chat.settings)["log_actions"]:
        names = {"ban": "🔨 забанен", "unban": "♻️ разбанен", "mute": "🔇 замучен", "unmute": "🔊 размучен",
                 "kick": "👢 исключён", "warn": "⚠️ получил предупреждение", "unwarn": "✔️ снято предупреждение"}
        actor = await users.ensure(session, v.id)
        text = f"{mention(target.id, target.username, target.display_name)} {names[body.action]}"
        if body.reason:
            text += f"\nПричина: {esc(body.reason)}"
        text += f"\n<i>через панель · {esc(actor.display_name)}</i>"
        try:
            await bot.send_message(chat.id, text)
        except TelegramAPIError:
            pass
    return {"ok": True}
