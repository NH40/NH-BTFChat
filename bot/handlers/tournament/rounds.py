from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import MIN_JUDGES_PER_MATCH
from bot.db import PlayerProfile
from bot.filters import IsTournamentAdmin
from bot.keyboards import vote_kb
from bot.services.tournament import matches as match_service
from bot.services.tournament import players as player_service
from bot.services.tournament import votes as vote_service
from bot.services.tournament.judges import select_random_judges
from bot.texts import tournament as texts

router = Router(name="tournament_rounds")


def _parse_match_id(args: str | None) -> int | None:
    if not args:
        return None
    try:
        return int(args.strip().split()[0])
    except ValueError:
        return None


async def _players(session: AsyncSession, match) -> tuple[PlayerProfile, PlayerProfile]:
    p1 = await session.get(PlayerProfile, match.player1_id)
    p2 = await session.get(PlayerProfile, match.player2_id)
    return p1, p2


async def _do_assign_random_judges(session: AsyncSession, match_id: int) -> str:
    match = await match_service.get_match(session, match_id)
    if match is None:
        return "Матч не найден."

    judges = await player_service.list_judges(session)
    eligible_ids = [j.id for j in judges]
    try:
        chosen_ids = select_random_judges(
            eligible_ids, {match.player1_id, match.player2_id}, MIN_JUDGES_PER_MATCH
        )
    except ValueError:
        return texts.NOT_ENOUGH_ELIGIBLE_JUDGES

    await match_service.assign_judges(session, match, chosen_ids)
    names = [j.display_name or str(j.tg_user_id) for j in judges if j.id in chosen_ids]
    return texts.JUDGES_ASSIGNED.format(names=", ".join(names))


@router.message(Command("pb_judges_random"), IsTournamentAdmin())
async def cmd_judges_random(message: Message, session: AsyncSession, command: CommandObject) -> None:
    match_id = _parse_match_id(command.args)
    if match_id is None:
        await message.answer("Формат: /pb_judges_random <id матча>")
        return
    await message.answer(await _do_assign_random_judges(session, match_id))


@router.callback_query(F.data.startswith("pb_judges_random:"), IsTournamentAdmin())
async def cb_judges_random(callback: CallbackQuery, session: AsyncSession) -> None:
    match_id = int(callback.data.split(":")[1])
    result_text = await _do_assign_random_judges(session, match_id)
    await callback.message.answer(result_text)
    await callback.answer()


@router.callback_query(F.data.startswith("pb_judges_random:"))
async def cb_judges_random_denied(callback: CallbackQuery) -> None:
    await callback.answer(texts.NOT_ADMIN, show_alert=True)


@router.message(Command("pb_next"), IsTournamentAdmin())
async def cmd_next(message: Message, session: AsyncSession, command: CommandObject) -> None:
    match_id = _parse_match_id(command.args)
    if match_id is None:
        await message.answer("Формат: /pb_next <id матча>")
        return

    match = await match_service.get_match(session, match_id)
    if match is None:
        await message.answer("Матч не найден.")
        return

    try:
        match = await match_service.advance_phase(session, match)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")
        return

    announcement = texts.ROUND_ANNOUNCE.get(match.status)
    if announcement:
        await message.answer(announcement)
    else:
        await message.answer(f"Матч #{match.id}: фаза «{match.status}».")

    if match.status == match_service.STATUS_ROUND_1:
        p1, p2 = await _players(session, match)
        p1_name = p1.display_name or str(p1.tg_user_id)
        p2_name = p2.display_name or str(p2.tg_user_id)
        await message.answer(
            texts.VOTE_PROMPT,
            reply_markup=vote_kb(match.id, p1.id, p1_name, p2.id, p2_name),
        )


@router.callback_query(F.data.startswith("pb_vote:"))
async def cb_vote(callback: CallbackQuery, session: AsyncSession) -> None:
    _, match_id_s, player_id_s = callback.data.split(":")
    match_id, voted_for_player_id = int(match_id_s), int(player_id_s)

    await vote_service.cast_vote(
        session, match_id=match_id, voter_tg_id=callback.from_user.id, voted_for_player_id=voted_for_player_id
    )
    await callback.answer(texts.VOTE_ACCEPTED)
