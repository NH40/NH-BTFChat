"""Команды модерации в группах: /ban /unban /mute /unmute /kick /warn /unwarn /warns /rules.

Цель — ответом на сообщение, либо первым аргументом @username / id. Срок — 30m / 2h / 1d / 1w
(без срока — навсегда), остальное — причина. Право: админ чата Telegram с правом ограничивать
(если разрешено настройкой чата) или старший/владелец команды BTF.
"""
from __future__ import annotations

from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Chat
from bot.db.models.users import ROLE_SENIOR
from bot.services import moderation, staff, users
from bot.services.moderation_settings import merged
from bot.utils.text import esc, mention
from bot.utils.time import human_duration, parse_duration

router = Router(name="moderation")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))


async def _can_moderate(bot: Bot, session: AsyncSession, chat: Chat, user_id: int) -> bool:
    if staff.at_least(await staff.role_of(session, user_id), ROLE_SENIOR):
        return True
    if not merged(chat.settings)["chat_admins_can_moderate"]:
        return False
    try:
        member = await bot.get_chat_member(chat.id, user_id)
    except TelegramAPIError:
        return False
    if member.status == ChatMemberStatus.CREATOR:
        return True
    return member.status == ChatMemberStatus.ADMINISTRATOR and bool(getattr(member, "can_restrict_members", False))


async def _target(message: Message, session: AsyncSession, args: list[str]) -> tuple[int | None, str, list[str]]:
    """(id цели, как её назвать, оставшиеся аргументы)."""
    reply = message.reply_to_message
    if reply and reply.from_user and not reply.from_user.is_bot:
        u = reply.from_user
        return u.id, mention(u.id, u.username, u.full_name), args
    if args:
        found = await users.resolve(session, args[0])
        if found is not None:
            return found.id, mention(found.id, found.username, found.display_name), args[1:]
        if args[0].lstrip("-").isdigit():
            return int(args[0]), f"<code>{esc(args[0])}</code>", args[1:]
    return None, "", args


def _duration_and_reason(args: list[str]) -> tuple[timedelta | None, str | None]:
    duration = parse_duration(args[0]) if args else None
    rest = args[1:] if duration else args
    return duration, (" ".join(rest).strip() or None)


async def _prepare(message: Message, command: CommandObject, session: AsyncSession, bot: Bot):
    chat = await session.get(Chat, message.chat.id)
    if chat is None:
        return None
    if not await _can_moderate(bot, session, chat, message.from_user.id):
        await message.reply("Недостаточно прав для модерации.")
        return None
    target_id, label, rest = await _target(message, session, (command.args or "").split())
    if target_id is None:
        await message.reply("Кого? Ответь на сообщение или укажи @username / id.")
        return None
    if target_id == message.from_user.id:
        await message.reply("Себя нельзя.")
        return None
    return chat, target_id, label, rest


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, rest = prep
    duration, reason = _duration_and_reason(rest)
    try:
        await moderation.ban(bot, session, chat.id, uid, message.from_user.id, duration, reason)
    except moderation.ModerationError as exc:
        await message.reply(f"Не получилось: {esc(exc)}")
        return
    await session.commit()
    await message.reply(f"⛔ {label} забанен ({human_duration(duration)})" + (f": {esc(reason)}" if reason else ""))


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, _ = prep
    try:
        await moderation.unban(bot, session, chat.id, uid, message.from_user.id)
    except moderation.ModerationError as exc:
        await message.reply(f"Не получилось: {esc(exc)}")
        return
    await session.commit()
    await message.reply(f"✅ {label} разбанен")


@router.message(Command("mute"))
async def cmd_mute(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, rest = prep
    duration, reason = _duration_and_reason(rest)
    try:
        await moderation.mute(bot, session, chat.id, uid, message.from_user.id, duration, reason)
    except moderation.ModerationError as exc:
        await message.reply(f"Не получилось: {esc(exc)}")
        return
    await session.commit()
    await message.reply(f"🔇 {label} в муте ({human_duration(duration)})" + (f": {esc(reason)}" if reason else ""))


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, _ = prep
    try:
        await moderation.unmute(bot, session, chat.id, uid, message.from_user.id)
    except moderation.ModerationError as exc:
        await message.reply(f"Не получилось: {esc(exc)}")
        return
    await session.commit()
    await message.reply(f"🔊 {label} может писать")


@router.message(Command("kick"))
async def cmd_kick(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, rest = prep
    reason = " ".join(rest).strip() or None
    try:
        await moderation.kick(bot, session, chat.id, uid, message.from_user.id, reason)
    except moderation.ModerationError as exc:
        await message.reply(f"Не получилось: {esc(exc)}")
        return
    await session.commit()
    await message.reply(f"👢 {label} исключён" + (f": {esc(reason)}" if reason else ""))


@router.message(Command("warn"))
async def cmd_warn(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, rest = prep
    reason = " ".join(rest).strip() or None
    try:
        res = await moderation.warn(bot, session, chat, uid, message.from_user.id, reason)
    except moderation.ModerationError as exc:
        await message.reply(f"Не получилось: {esc(exc)}")
        return
    await session.commit()
    text = f"⚠️ {label}: предупреждение {res.count}/{res.limit}" + (f" — {esc(reason)}" if reason else "")
    if res.punished:
        text += f"\nЛимит достигнут — {'бан' if res.punished == 'ban' else 'мут'}."
    await message.reply(text)


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    prep = await _prepare(message, command, session, bot)
    if prep is None:
        return
    chat, uid, label, _ = prep
    left = await moderation.unwarn(session, chat.id, uid, message.from_user.id)
    await session.commit()
    await message.reply(f"↩️ {label}: снято предупреждение, осталось {left}")


@router.message(Command("warns"))
async def cmd_warns(message: Message, command: CommandObject, session: AsyncSession, bot: Bot) -> None:
    chat = await session.get(Chat, message.chat.id)
    if chat is None:
        return
    uid, label, _ = await _target(message, session, (command.args or "").split())
    if uid is None:
        uid, label = message.from_user.id, mention(message.from_user.id, message.from_user.username, message.from_user.full_name)
    cfg = merged(chat.settings)["warns"]
    count = await moderation.active_warns(session, chat.id, uid, cfg["expire_days"])
    await message.reply(f"⚠️ {label}: {count}/{cfg['limit']} предупреждений")


@router.message(Command("rules"))
async def cmd_rules(message: Message, session: AsyncSession) -> None:
    chat = await session.get(Chat, message.chat.id)
    rules = merged(chat.settings)["rules"] if chat else ""
    await message.reply(esc(rules) if rules else "Правила ещё не заданы.")
