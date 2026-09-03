from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsTournamentAdmin
from bot.services.tournament import chat as chat_service
from bot.services.tournament import players as player_service
from bot.services.tournament import seasons as season_service
from bot.services.tournament import universes as universe_service
from bot.texts import tournament as texts

router = Router(name="tournament_admin")

ADMIN_STATUSES = {"administrator", "creator"}


def _display_name(user) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


@router.message(Command("pb_register_chat"))
async def cmd_register_chat(message: Message, session: AsyncSession, bot: Bot) -> None:
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Эту команду нужно вызывать в групповом чате, который станет турнирным.")
        return

    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ADMIN_STATUSES:
        await message.answer(texts.MUST_BE_TG_ADMIN_TO_REGISTER)
        return

    existing_chat_id = await chat_service.get_registered_chat_id(session)
    if existing_chat_id and existing_chat_id != message.chat.id:
        await message.answer(texts.CHAT_ALREADY_REGISTERED_ELSEWHERE)
        return

    await chat_service.register_chat(
        session,
        tg_chat_id=message.chat.id,
        title=message.chat.title,
        registered_by_tg_id=message.from_user.id,
    )
    if not await chat_service.has_any_admin(session):
        await chat_service.add_admin(session, message.from_user.id, added_by_tg_id=message.from_user.id)

    await message.answer(texts.CHAT_REGISTERED)


@router.message(Command("pb_admin_add"), IsTournamentAdmin())
async def cmd_admin_add(message: Message, session: AsyncSession) -> None:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(texts.REPLY_REQUIRED)
        return
    target = message.reply_to_message.from_user
    await chat_service.add_admin(session, target.id, added_by_tg_id=message.from_user.id)
    await message.answer(texts.ADMIN_ADDED.format(name=_display_name(target)))


@router.message(Command("pb_admin_remove"), IsTournamentAdmin())
async def cmd_admin_remove(message: Message, session: AsyncSession) -> None:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(texts.REPLY_REQUIRED)
        return
    target = message.reply_to_message.from_user
    await chat_service.remove_admin(session, target.id)
    await message.answer(texts.ADMIN_REMOVED.format(name=_display_name(target)))


@router.message(Command("pb_universe_add"), IsTournamentAdmin())
async def cmd_universe_add(message: Message, session: AsyncSession, command: CommandObject) -> None:
    name = (command.args or "").strip()
    if not name:
        await message.answer("Формат: /pb_universe_add <название>")
        return

    existing = await universe_service.get_universe_by_name(session, name)
    if existing:
        await message.answer(texts.UNIVERSE_EXISTS)
        return

    await universe_service.create_universe(session, name=name, created_by_tg_id=message.from_user.id)
    await message.answer(texts.UNIVERSE_ADDED.format(name=name))


@router.message(Command("pb_universes"))
async def cmd_universes(message: Message, session: AsyncSession) -> None:
    universes = await universe_service.list_universes(session)
    if not universes:
        await message.answer(texts.NO_UNIVERSES)
        return
    lines = [f"• {u.name}" for u in universes]
    await message.answer("Вселенные:\n" + "\n".join(lines))


@router.message(Command("pb_char_add"), IsTournamentAdmin())
async def cmd_char_add(message: Message, session: AsyncSession, command: CommandObject) -> None:
    raw = command.args or ""
    if "|" not in raw:
        await message.answer("Формат: /pb_char_add <вселенная> | <персонаж>")
        return

    universe_name, char_name = (part.strip() for part in raw.split("|", 1))
    universe = await universe_service.get_universe_by_name(session, universe_name)
    if not universe:
        await message.answer(texts.UNIVERSE_NOT_FOUND.format(name=universe_name))
        return

    await universe_service.add_character(session, universe_id=universe.id, name=char_name)
    await message.answer(texts.CHARACTER_ADDED.format(name=char_name, universe=universe.name))


@router.message(Command("pb_char_remove"), IsTournamentAdmin())
async def cmd_char_remove(message: Message, session: AsyncSession, command: CommandObject) -> None:
    raw = command.args or ""
    if "|" not in raw:
        await message.answer("Формат: /pb_char_remove <вселенная> | <персонаж>")
        return

    universe_name, char_name = (part.strip() for part in raw.split("|", 1))
    universe = await universe_service.get_universe_by_name(session, universe_name)
    if not universe:
        await message.answer(texts.UNIVERSE_NOT_FOUND.format(name=universe_name))
        return

    characters = await universe_service.list_characters(session, universe.id)
    match = next((c for c in characters if c.name.lower() == char_name.lower()), None)
    if not match:
        await message.answer(texts.CHARACTER_NOT_FOUND.format(name=char_name))
        return

    await universe_service.remove_character(session, match.id)
    await message.answer(texts.CHARACTER_REMOVED.format(name=char_name))


@router.message(Command("pb_char_list"))
async def cmd_char_list(message: Message, session: AsyncSession, command: CommandObject) -> None:
    universe_name = (command.args or "").strip()
    universe = await universe_service.get_universe_by_name(session, universe_name)
    if not universe:
        await message.answer(texts.UNIVERSE_NOT_FOUND.format(name=universe_name))
        return

    characters = await universe_service.list_characters(session, universe.id)
    if not characters:
        await message.answer("В этой вселенной пока нет персонажей.")
        return
    lines = [f"#{c.id} {c.name}" for c in characters]
    await message.answer(f"Персонажи «{universe.name}»:\n" + "\n".join(lines))


@router.message(Command("pb_judge_add"), IsTournamentAdmin())
async def cmd_judge_add(message: Message, session: AsyncSession) -> None:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(texts.REPLY_REQUIRED)
        return
    target = message.reply_to_message.from_user
    await player_service.get_or_create_player(session, target.id, _display_name(target))
    await player_service.set_judge_flag(session, target.id, True)
    await message.answer(texts.JUDGE_ADDED.format(name=_display_name(target)))


@router.message(Command("pb_judge_remove"), IsTournamentAdmin())
async def cmd_judge_remove(message: Message, session: AsyncSession) -> None:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(texts.REPLY_REQUIRED)
        return
    target = message.reply_to_message.from_user
    await player_service.set_judge_flag(session, target.id, False)
    await message.answer(texts.JUDGE_REMOVED.format(name=_display_name(target)))


@router.message(Command("pb_judges"))
async def cmd_judges_list(message: Message, session: AsyncSession) -> None:
    judges = await player_service.list_judges(session)
    if not judges:
        await message.answer(texts.NO_JUDGES)
        return
    lines = [f"• {j.display_name or j.tg_user_id} (отсужено: {j.judge_matches_count})" for j in judges]
    await message.answer("Судьи:\n" + "\n".join(lines))


@router.message(Command("pb_season_new"), IsTournamentAdmin())
async def cmd_season_new(message: Message, session: AsyncSession, command: CommandObject) -> None:
    name = (command.args or "").strip()
    if not name:
        await message.answer("Формат: /pb_season_new <название>")
        return
    await season_service.start_season(session, name)
    await message.answer(texts.SEASON_STARTED.format(name=name))


@router.message(Command("pb_season_reset"), IsTournamentAdmin())
async def cmd_season_reset(message: Message, session: AsyncSession) -> None:
    count = await season_service.reset_all_ratings(session)
    await message.answer(texts.SEASON_RESET_DONE.format(count=count))
