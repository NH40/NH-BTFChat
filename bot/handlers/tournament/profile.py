from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.tournament import players as player_service
from bot.texts import tournament as texts

router = Router(name="tournament_profile")


def _display_name(user) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


@router.message(Command("pb_profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    target_user = message.from_user
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    player = await player_service.get_or_create_player(session, target_user.id, _display_name(target_user))

    await message.answer(
        texts.PROFILE_TEMPLATE.format(
            name=player.display_name or target_user.id,
            elo=player.elo,
            wins=player.wins,
            losses=player.losses,
            draws=player.draws,
            judge_matches=player.judge_matches_count,
            judge_status="да ⚖️" if player.is_judge else "нет",
        )
    )


@router.message(Command("pb_top"))
async def cmd_top(message: Message, session: AsyncSession) -> None:
    board = await player_service.leaderboard(session, limit=10)
    if not board:
        await message.answer("Пока нет ни одного игрока в рейтинге.")
        return

    lines = [
        texts.TOP_ROW.format(place=i + 1, name=p.display_name or p.tg_user_id, elo=p.elo)
        for i, p in enumerate(board)
    ]
    await message.answer(texts.TOP_HEADER + "\n".join(lines))
