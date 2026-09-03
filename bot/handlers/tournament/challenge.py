import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import BAN_COUNT_PER_PLAYER
from bot.db import PlayerProfile
from bot.keyboards import ban_phase_kb, judges_random_kb
from bot.services.tournament import matches as match_service
from bot.services.tournament import players as player_service
from bot.services.tournament import universes as universe_service
from bot.texts import tournament as texts

router = Router(name="tournament_challenge")
logger = logging.getLogger(__name__)

_MIN_POOL_SIZE = 2 + 2 * BAN_COUNT_PER_PLAYER


def _display_name(user) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


@router.message(Command("pb_challenge"))
async def cmd_challenge(message: Message, session: AsyncSession, command: CommandObject) -> None:
    universe_name = (command.args or "").strip()
    if not universe_name or not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(texts.CHALLENGE_USAGE)
        return

    opponent_user = message.reply_to_message.from_user
    if opponent_user.id == message.from_user.id:
        await message.answer(texts.CHALLENGE_SELF_ERROR)
        return

    universe = await universe_service.get_universe_by_name(session, universe_name)
    if not universe:
        await message.answer(texts.UNIVERSE_NOT_FOUND.format(name=universe_name))
        return

    characters = await universe_service.list_characters(session, universe.id)
    if len(characters) < _MIN_POOL_SIZE:
        await message.answer(texts.NOT_ENOUGH_CHARACTERS.format(min_count=_MIN_POOL_SIZE))
        return

    p1 = await player_service.get_or_create_player(
        session, message.from_user.id, _display_name(message.from_user)
    )
    p2 = await player_service.get_or_create_player(session, opponent_user.id, _display_name(opponent_user))

    match = await match_service.create_match(
        session,
        universe_id=universe.id,
        player1_id=p1.id,
        player2_id=p2.id,
        chat_id=message.chat.id,
        created_by_tg_id=message.from_user.id,
    )

    announce = texts.CHALLENGE_ANNOUNCE.format(
        universe=universe.name,
        p1=p1.display_name,
        p2=p2.display_name,
        ban_count=BAN_COUNT_PER_PLAYER,
    )
    await message.answer(
        f"{announce}\n\n<i>id матча: {match.id}</i>", reply_markup=ban_phase_kb(match.id, characters)
    )


@router.callback_query(F.data.startswith("pb_ban:"))
async def cb_ban(callback: CallbackQuery, session: AsyncSession) -> None:
    _, match_id_s, character_id_s = callback.data.split(":")
    match_id, character_id = int(match_id_s), int(character_id_s)

    match = await match_service.get_match(session, match_id)
    if match is None:
        await callback.answer("Матч не найден.", show_alert=True)
        return

    player = await player_service.get_player_by_tg_id(session, callback.from_user.id)
    if player is None or player.id not in (match.player1_id, match.player2_id):
        await callback.answer(texts.BAN_NOT_A_PLAYER, show_alert=True)
        return

    if len(match_service.player_bans(match, player.id)) >= BAN_COUNT_PER_PLAYER:
        await callback.answer(texts.BAN_ALREADY_DONE, show_alert=True)
        return

    character = await universe_service.get_character(session, character_id)
    if character is None or character.universe_id != match.universe_id:
        await callback.answer("Некорректный персонаж.", show_alert=True)
        return

    try:
        await match_service.submit_ban(session, match, player.id, character_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.answer("Бан принят")
    await callback.message.answer(
        texts.BAN_ACCEPTED.format(player=player.display_name, character=character.name)
    )

    if not match_service.bans_complete(match):
        return

    try:
        pick1, pick2 = await match_service.assign_random_characters(session, match)
    except ValueError as exc:
        logger.exception("Failed to assign random characters for match %s", match.id)
        await callback.message.answer(f"⚠️ Не удалось раздать персонажей: {exc}")
        return

    char1 = await universe_service.get_character(session, pick1.character_id)
    char2 = await universe_service.get_character(session, pick2.character_id)
    player1 = await session.get(PlayerProfile, match.player1_id)
    player2 = await session.get(PlayerProfile, match.player2_id)

    await callback.message.answer(
        texts.BANS_COMPLETE_ANNOUNCE.format(
            p1=player1.display_name, c1=char1.name, p2=player2.display_name, c2=char2.name
        ),
        reply_markup=judges_random_kb(match.id),
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
