"""Общие настройки: напоминания по умолчанию для новых задач, чат админов/служебный (только чтение —
назначаются в разделе «Чаты»)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, get_session, senior, viewer
from api.routers.tasks import ReminderIn
from api.serializers import chat_out
from bot.config import settings as app_config
from bot.db import Chat
from bot.services import app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


async def _chat(session: AsyncSession, key: str) -> dict | None:
    chat_id = (await app_settings.get(session, key)).get("chat_id")
    chat = await session.get(Chat, chat_id) if chat_id else None
    return chat_out(chat) if chat else None


@router.get("")
async def get_all(v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    return {
        "timezone": app_config.timezone,
        "admin_chat": await _chat(session, app_settings.KEY_ADMIN_CHAT),
        "service_chat": await _chat(session, app_settings.KEY_SERVICE_CHAT),
        "reminder_defaults": (await app_settings.get(session, app_settings.KEY_REMINDER_DEFAULTS))["items"],
    }


class DefaultsIn(BaseModel):
    items: list[ReminderIn]


@router.put("/reminder-defaults")
async def put_defaults(body: DefaultsIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    # «В конкретное время» для всех задач сразу смысла не имеет — его не сохраняем.
    items = [r.model_dump(exclude={"at"}) for r in body.items if r.kind != "at"]
    await app_settings.put(session, app_settings.KEY_REMINDER_DEFAULTS, {"items": items})
    await session.commit()
    return {"ok": True}
