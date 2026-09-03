from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant import SCORE_CATEGORIES
from bot.db import PlayerProfile
from bot.filters import IsTournamentAdmin
from bot.services.tournament import matches as match_service
from bot.services.tournament import players as player_service
from bot.states import JudgeScoring
from bot.texts import tournament as texts

router = Router(name="tournament_scoring")

_CATEGORY_LABELS = {
    "evidence": "доказательная база",
    "argumentation": "аргументация",
    "scaling": "scaling",
    "defense": "защита (Round 2)",
    "attack": "атака (Round 3)",
    "math": "математика/физика",
    "structure": "структура и подача",
}

_STEP_ORDER = [
    (JudgeScoring.p1_evidence, "p1", "evidence"),
    (JudgeScoring.p1_argumentation, "p1", "argumentation"),
    (JudgeScoring.p1_scaling, "p1", "scaling"),
    (JudgeScoring.p1_defense, "p1", "defense"),
    (JudgeScoring.p1_attack, "p1", "attack"),
    (JudgeScoring.p1_math, "p1", "math"),
    (JudgeScoring.p1_structure, "p1", "structure"),
    (JudgeScoring.p2_evidence, "p2", "evidence"),
    (JudgeScoring.p2_argumentation, "p2", "argumentation"),
    (JudgeScoring.p2_scaling, "p2", "scaling"),
    (JudgeScoring.p2_defense, "p2", "defense"),
    (JudgeScoring.p2_attack, "p2", "attack"),
    (JudgeScoring.p2_math, "p2", "math"),
    (JudgeScoring.p2_structure, "p2", "structure"),
]
_CANCEL_WORDS = {"/cancel", "cancel", "отмена"}


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


async def _ask_step(message: Message, data: dict, step: tuple) -> None:
    _, target_key, category_key = step
    player_name = data["p1_name"] if target_key == "p1" else data["p2_name"]
    max_value = SCORE_CATEGORIES[category_key]
    await message.answer(
        texts.SCORE_ASK.format(player=player_name, category=_CATEGORY_LABELS[category_key], max_value=max_value)
    )


@router.message(Command("pb_score"))
async def cmd_score_start(
    message: Message, session: AsyncSession, state: FSMContext, command: CommandObject
) -> None:
    match_id = _parse_match_id(command.args)
    if match_id is None:
        await message.answer("Формат: /pb_score <id матча>")
        return

    match = await match_service.get_match(session, match_id)
    if match is None:
        await message.answer("Матч не найден.")
        return
    if match.status != match_service.STATUS_JUDGING:
        await message.answer("Этот матч сейчас не в фазе судейства.")
        return

    judge = await player_service.get_player_by_tg_id(session, message.from_user.id)
    if judge is None or judge.id not in {j.judge_player_id for j in match.judges}:
        await message.answer("Ты не назначен(а) судьёй этого матча.")
        return

    p1, p2 = await _players(session, match)
    p1_name = p1.display_name or str(p1.tg_user_id)
    p2_name = p2.display_name or str(p2.tg_user_id)

    await state.set_state(_STEP_ORDER[0][0])
    await state.update_data(
        match_id=match.id,
        judge_player_id=judge.id,
        p1_id=p1.id,
        p2_id=p2.id,
        p1_name=p1_name,
        p2_name=p2_name,
        scores={"p1": {}, "p2": {}},
    )

    await message.answer(texts.SCORE_START.format(match_id=match.id, p1=p1_name, p2=p2_name))
    data = await state.get_data()
    await _ask_step(message, data, _STEP_ORDER[0])


@router.message(StateFilter(*[step[0] for step in _STEP_ORDER]))
async def process_score_step(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    raw_text = (message.text or "").strip()
    if raw_text.lower() in _CANCEL_WORDS:
        await state.clear()
        await message.answer("Судейство отменено.")
        return

    current_state_name = await state.get_state()
    step_index = next(i for i, (s, _, _) in enumerate(_STEP_ORDER) if s.state == current_state_name)
    _, target_key, category_key = _STEP_ORDER[step_index]
    max_value = SCORE_CATEGORIES[category_key]

    try:
        value = int(raw_text)
        if not 0 <= value <= max_value:
            raise ValueError
    except ValueError:
        await message.answer(texts.SCORE_INVALID_NUMBER.format(max_value=max_value))
        return

    data = await state.get_data()
    scores = data["scores"]
    scores[target_key][category_key] = value
    await state.update_data(scores=scores)

    next_index = step_index + 1
    if next_index < len(_STEP_ORDER):
        await state.set_state(_STEP_ORDER[next_index][0])
        await _ask_step(message, data, _STEP_ORDER[next_index])
        return

    match = await match_service.get_match(session, data["match_id"])
    if match is None or match.status != match_service.STATUS_JUDGING:
        await state.clear()
        await message.answer("⚠️ Матч больше не в фазе судейства, баллы не сохранены.")
        return

    await match_service.submit_score(
        session, match, judge_player_id=data["judge_player_id"], target_player_id=data["p1_id"], scores=scores["p1"]
    )
    await match_service.submit_score(
        session, match, judge_player_id=data["judge_player_id"], target_player_id=data["p2_id"], scores=scores["p2"]
    )

    await message.answer(texts.SCORE_SAVED.format(player=data["p1_name"], total=sum(scores["p1"].values())))
    await message.answer(texts.SCORE_SAVED.format(player=data["p2_name"], total=sum(scores["p2"].values())))

    match = await match_service.get_match(session, data["match_id"])
    judge_ids = {j.judge_player_id for j in match.judges}
    progress = match_service.scoring_progress(match)
    targets = {match.player1_id, match.player2_id}
    done_count = sum(1 for jid in judge_ids if progress.get(jid, set()) == targets)

    await message.answer(
        texts.SCORE_ALL_SUBMITTED_WAITING.format(done=done_count, needed=len(judge_ids), match_id=match.id)
    )
    await state.clear()


@router.message(Command("pb_finalize"), IsTournamentAdmin())
async def cmd_finalize(
    message: Message, session: AsyncSession, command: CommandObject, bot: Bot
) -> None:
    match_id = _parse_match_id(command.args)
    if match_id is None:
        await message.answer("Формат: /pb_finalize <id матча>")
        return

    match = await match_service.get_match(session, match_id)
    if match is None:
        await message.answer("Матч не найден.")
        return
    if not match_service.scores_complete(match):
        await message.answer(texts.FINALIZE_NOT_READY)
        return

    p1_before, p2_before = await _players(session, match)
    elo1_before, elo2_before = p1_before.elo, p2_before.elo
    p1_name = p1_before.display_name or str(p1_before.tg_user_id)
    p2_name = p2_before.display_name or str(p2_before.tg_user_id)

    try:
        outcome = await match_service.finalize_match(session, match)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")
        return

    p1_after, p2_after = await _players(session, match)

    if outcome.winner == 1:
        winner_line = texts.FINALIZE_WINNER_LINE.format(winner=p1_name)
    elif outcome.winner == 2:
        winner_line = texts.FINALIZE_WINNER_LINE.format(winner=p2_name)
    else:
        winner_line = texts.FINALIZE_DRAW_LINE

    total_votes = outcome.player1_viewer_votes + outcome.player2_viewer_votes
    p1_vote_share = (outcome.player1_viewer_votes / total_votes) if total_votes else 0.5
    p2_vote_share = 1 - p1_vote_share

    text = texts.FINALIZE_ANNOUNCE.format(
        p1=p1_name,
        p2=p2_name,
        p1_avg=outcome.player1_judge_avg,
        p2_avg=outcome.player2_judge_avg,
        p1_votes=outcome.player1_viewer_votes,
        p2_votes=outcome.player2_viewer_votes,
        p1_share=p1_vote_share,
        p2_share=p2_vote_share,
        p1_weighted=outcome.player1_weighted,
        p2_weighted=outcome.player2_weighted,
        winner_line=winner_line,
        elo1_before=elo1_before,
        elo1_after=p1_after.elo,
        elo1_delta=p1_after.elo - elo1_before,
        elo2_before=elo2_before,
        elo2_after=p2_after.elo,
        elo2_delta=p2_after.elo - elo2_before,
    )
    await bot.send_message(match.chat_id, text)
    if message.chat.id != match.chat_id:
        await message.answer("Итоги объявлены в турнирном чате ✅")
