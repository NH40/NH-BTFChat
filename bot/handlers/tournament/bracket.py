from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import DEFAULT_BRACKET_SLOTS
from bot.db import PlayerProfile
from bot.filters import IsTournamentAdmin
from bot.keyboards import tournament_join_kb
from bot.services.tournament import chat as chat_service
from bot.services.tournament import players as player_service
from bot.services.tournament import tournaments as tournament_service
from bot.services.tournament import universes as universe_service
from bot.texts import tournament as texts

router = Router(name="tournament_bracket")


def _display_name(user) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


def _parse_id(args: str | None) -> int | None:
    if not args:
        return None
    try:
        return int(args.strip().split()[0])
    except ValueError:
        return None


async def _pairs_text(session: AsyncSession, matches) -> str:
    lines = []
    for m in matches:
        p1 = await session.get(PlayerProfile, m.player1_id)
        p2 = await session.get(PlayerProfile, m.player2_id)
        lines.append(f"#{m.id}: {p1.display_name} 🆚 {p2.display_name}")
    return "\n".join(lines)


@router.message(Command("pb_tournament_new"), IsTournamentAdmin())
async def cmd_tournament_new(
    message: Message, session: AsyncSession, command: CommandObject, bot: Bot
) -> None:
    raw = command.args or ""
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2:
        await message.answer(
            "Формат: /pb_tournament_new <название> | <вселенная> | [слотов, по умолчанию 8]"
        )
        return

    name, universe_name = parts[0], parts[1]
    slots = DEFAULT_BRACKET_SLOTS
    if len(parts) >= 3 and parts[2]:
        try:
            slots = int(parts[2])
        except ValueError:
            await message.answer("Число слотов должно быть целым (2, 4, 8, 16...).")
            return

    universe = await universe_service.get_universe_by_name(session, universe_name)
    if not universe:
        await message.answer(texts.UNIVERSE_NOT_FOUND.format(name=universe_name))
        return

    chat_id = await chat_service.get_registered_chat_id(session)
    if not chat_id:
        await message.answer(texts.NO_CHAT_REGISTERED)
        return

    try:
        tournament = await tournament_service.create_tournament(
            session,
            name=name,
            chat_id=chat_id,
            created_by_tg_id=message.from_user.id,
            universe_id=universe.id,
            slots=slots,
        )
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")
        return

    text = texts.TOURNAMENT_ANNOUNCE.format(
        name=tournament.name, universe=universe.name, joined=0, slots=tournament.slots, id=tournament.id
    )
    await bot.send_message(chat_id, text, reply_markup=tournament_join_kb(tournament.id))
    if message.chat.id != chat_id:
        await message.answer(
            texts.TOURNAMENT_CREATED.format(name=tournament.name, slots=tournament.slots, id=tournament.id)
        )


async def _do_join(session: AsyncSession, tournament_id: int, tg_user_id: int, display_name: str):
    tournament = await tournament_service.get_tournament(session, tournament_id)
    if tournament is None:
        return "Турнир не найден.", None

    player = await player_service.get_or_create_player(session, tg_user_id, display_name)
    try:
        await tournament_service.join_tournament(session, tournament, player.id)
    except ValueError as exc:
        return str(exc), tournament

    tournament = await tournament_service.get_tournament(session, tournament_id)
    return None, tournament


@router.message(Command("pb_join_tournament"))
async def cmd_join_tournament(message: Message, session: AsyncSession, command: CommandObject) -> None:
    tournament_id = _parse_id(command.args)
    if tournament_id is None:
        await message.answer("Формат: /pb_join_tournament <id турнира>")
        return

    error, tournament = await _do_join(
        session, tournament_id, message.from_user.id, _display_name(message.from_user)
    )
    if error:
        await message.answer(error)
        return

    await message.answer(
        texts.TOURNAMENT_JOINED.format(name=tournament.name, joined=len(tournament.signups), slots=tournament.slots)
    )
    if tournament_service.is_full(tournament):
        await message.answer(texts.TOURNAMENT_FULL_ANNOUNCE.format(slots=tournament.slots, id=tournament.id))


@router.callback_query(F.data.startswith("pb_join_t:"))
async def cb_join_tournament(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    tournament_id = int(callback.data.split(":")[1])
    error, tournament = await _do_join(
        session, tournament_id, callback.from_user.id, _display_name(callback.from_user)
    )
    if error:
        await callback.answer(error, show_alert=True)
        return

    universe_name = "любая"
    if tournament.universe_id:
        universe = await universe_service.get_universe_with_characters(session, tournament.universe_id)
        if universe:
            universe_name = universe.name

    text = texts.TOURNAMENT_ANNOUNCE.format(
        name=tournament.name,
        universe=universe_name,
        joined=len(tournament.signups),
        slots=tournament.slots,
        id=tournament.id,
    )
    is_full = tournament_service.is_full(tournament)
    try:
        await callback.message.edit_text(text, reply_markup=None if is_full else tournament_join_kb(tournament.id))
    except TelegramBadRequest:
        pass

    await callback.answer(
        texts.TOURNAMENT_JOINED.format(name=tournament.name, joined=len(tournament.signups), slots=tournament.slots)
    )
    if is_full:
        await bot.send_message(
            tournament.chat_id, texts.TOURNAMENT_FULL_ANNOUNCE.format(slots=tournament.slots, id=tournament.id)
        )


@router.message(Command("pb_tournament_start"), IsTournamentAdmin())
async def cmd_tournament_start(
    message: Message, session: AsyncSession, command: CommandObject, bot: Bot
) -> None:
    tournament_id = _parse_id(command.args)
    if tournament_id is None:
        await message.answer("Формат: /pb_tournament_start <id турнира>")
        return

    tournament = await tournament_service.get_tournament(session, tournament_id)
    if tournament is None:
        await message.answer("Турнир не найден.")
        return

    try:
        matches = await tournament_service.start_bracket(session, tournament)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")
        return

    pairs = await _pairs_text(session, matches)
    await bot.send_message(tournament.chat_id, texts.TOURNAMENT_BRACKET_STARTED.format(pairs=pairs))


@router.message(Command("pb_tournament_advance"), IsTournamentAdmin())
async def cmd_tournament_advance(
    message: Message, session: AsyncSession, command: CommandObject, bot: Bot
) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        await message.answer("Формат: /pb_tournament_advance <id турнира> <номер раунда>")
        return
    try:
        tournament_id, round_number = int(args[0]), int(args[1])
    except ValueError:
        await message.answer("id турнира и номер раунда должны быть числами.")
        return

    tournament = await tournament_service.get_tournament(session, tournament_id)
    if tournament is None:
        await message.answer("Турнир не найден.")
        return

    try:
        new_matches, champion_player_id = await tournament_service.advance_round(
            session, tournament, round_number
        )
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")
        return

    if champion_player_id is not None:
        champion = await session.get(PlayerProfile, champion_player_id)
        await bot.send_message(
            tournament.chat_id,
            texts.TOURNAMENT_CHAMPION.format(name=tournament.name, champion=champion.display_name),
        )
        return

    pairs = await _pairs_text(session, new_matches)
    await bot.send_message(
        tournament.chat_id, texts.TOURNAMENT_ROUND_ADVANCE.format(round=round_number, pairs=pairs)
    )
