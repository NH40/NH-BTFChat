from bot.constant import (
    BAN_COUNT_PER_PLAYER,
    FINAL_STATEMENT_P1_MINUTES,
    FINAL_STATEMENT_P2_MINUTES,
    MIN_JUDGES_PER_MATCH,
    PREP_MAX_HOURS,
    ROUND1_MINUTES_PER_PLAYER,
    ROUND2_MINUTES_PER_PLAYER,
    ROUND3_MINUTES_PER_PLAYER,
    VERDICT_MINUTES,
)

NOT_ADMIN = "🚫 Эта команда доступна только организаторам турнира."
NO_CHAT_REGISTERED = (
    "Турнирный чат ещё не зарегистрирован. Организатор должен вызвать /pb_register_chat в нужном чате."
)
CHAT_REGISTERED = "✅ Этот чат зарегистрирован как турнирный. Ты назначен(а) первым организатором."
CHAT_ALREADY_REGISTERED_ELSEWHERE = "Турнирный чат уже зарегистрирован. Повторная регистрация не нужна."
MUST_BE_TG_ADMIN_TO_REGISTER = "Зарегистрировать турнирный чат может только администратор этого чата в Telegram."

ADMIN_ADDED = "✅ {name} теперь организатор турниров."
ADMIN_REMOVED = "✅ {name} больше не организатор турниров."
REPLY_REQUIRED = "Ответь этой командой на сообщение нужного пользователя."

UNIVERSE_EXISTS = "Такая вселенная уже добавлена."
UNIVERSE_ADDED = "✅ Вселенная «{name}» добавлена."
UNIVERSE_NOT_FOUND = "Вселенная «{name}» не найдена. Проверь список: /pb_universes"
NO_UNIVERSES = "Пока не добавлено ни одной вселенной. Добавь: /pb_universe_add <название>"

CHARACTER_ADDED = "✅ Персонаж «{name}» добавлен во вселенную «{universe}»."
CHARACTER_NOT_FOUND = "Персонаж «{name}» не найден в этой вселенной."
CHARACTER_REMOVED = "🗑 Персонаж «{name}» удалён."
NOT_ENOUGH_CHARACTERS = (
    "В этой вселенной слишком мало персонажей для матча (нужно минимум {min_count} "
    "с учётом банов, включая доступные после бана)."
)

JUDGE_ADDED = "⚖️ {name} теперь в пуле судей."
JUDGE_REMOVED = "⚖️ {name} исключён(а) из пула судей."
NO_JUDGES = "Пул судей пуст. Добавь судей: ответь на сообщение пользователя командой /pb_judge_add"

PROFILE_TEMPLATE = (
    "👤 <b>{name}</b>\n"
    "Эло: <b>{elo}</b>\n"
    "Побед: {wins} | Поражений: {losses} | Ничьих: {draws}\n"
    "Отсужено матчей: {judge_matches}\n"
    "Статус судьи: {judge_status}"
)

TOP_HEADER = "🏆 Топ игроков по Эло:\n"
TOP_ROW = "{place}. {name} — {elo}"

CHALLENGE_USAGE = (
    "Формат: /pb_challenge <вселенная> — ответом на сообщение соперника, "
    "или /pb_challenge <вселенная> @username"
)
CHALLENGE_SELF_ERROR = "Нельзя вызвать самого себя на бой."
CHALLENGE_ANNOUNCE = (
    "⚔️ <b>POWER BATTLE</b>\n\n"
    "Вселенная: <b>{universe}</b>\n"
    "{p1} 🆚 {p2}\n\n"
    "Фаза банов: у каждого игрока {ban_count} бана. Жмите на персонажей ниже, чтобы забанить."
)
BAN_NOT_A_PLAYER = "Баны может ставить только один из участников этого матча."
BAN_ALREADY_DONE = "Ты уже использовал(а) все баны."
BAN_ACCEPTED = "🚫 {player} банит: {character}"
BANS_COMPLETE_ANNOUNCE = (
    "✅ Баны завершены. Персонажи розданы случайно из оставшегося пула:\n\n{p1} — {c1}\n{p2} — {c2}\n\n"
    f"⏳ Подготовка: до {PREP_MAX_HOURS} часов. Организатор запускает раунды командой /pb_next <id>."
)

ROUND_ANNOUNCE = {
    "round_1": f"🎤 <b>Раунд 1 — Presentation</b>\nПо {ROUND1_MINUTES_PER_PLAYER} мин. на игрока.",
    "round_2": f"🛡 <b>Раунд 2 — Defense</b>\nПо {ROUND2_MINUTES_PER_PLAYER} мин. на игрока.",
    "round_3": f"⚔️ <b>Раунд 3 — Attack</b>\nПо {ROUND3_MINUTES_PER_PLAYER} мин. на игрока.",
    "final_statement": (
        f"🏁 <b>Финальное слово</b>\n{FINAL_STATEMENT_P1_MINUTES} мин. первому игроку, "
        f"{FINAL_STATEMENT_P2_MINUTES} мин. второму."
    ),
    "judging": f"⚖️ <b>Судейство</b>\nСудьи, вносите баллы: /pb_score <id матча> (в личных сообщениях боту). "
    f"На вердикт даётся {VERDICT_MINUTES} мин.",
}
TIME_UP_REMINDER = "⏰ Время фазы «{phase}» вышло! Организатор, переходи дальше: /pb_next {match_id}"

JUDGES_NEED_MORE = f"Нужно назначить минимум {MIN_JUDGES_PER_MATCH} судей: /pb_judges_random {{match_id}}"
JUDGES_ASSIGNED = "⚖️ Судьи матча: {names}"
NOT_ENOUGH_ELIGIBLE_JUDGES = "В пуле недостаточно судей, не участвующих в этом матче."

SCORE_START = (
    "Судейство матча #{match_id}: {p1} 🆚 {p2}\n\n"
    "Сейчас спрошу баллы по {p1} (0-100 в сумме по категориям), затем по {p2}.\n"
    "Отправляй числа по одной категории за раз. /cancel — отменить."
)
SCORE_ASK = "{player} — {category} (0-{max_value}):"
SCORE_INVALID_NUMBER = "Нужно целое число от 0 до {max_value}. Попробуй ещё раз."
SCORE_SAVED = "✅ Баллы за {player} сохранены: {total}/100."
SCORE_ALL_SUBMITTED_WAITING = (
    "Спасибо! Ждём остальных судей ({done}/{needed}). Как только все сдадут баллы — "
    "организатор сможет подвести итог: /pb_finalize {match_id}"
)

FINALIZE_NOT_READY = "Не все судьи сдали баллы по обоим игрокам."
FINALIZE_ANNOUNCE = (
    "🏆 <b>Итоги Power Battle</b>\n\n"
    "{p1}: судьи {p1_avg:.1f}/100, голоса зрителей {p1_votes} ({p1_share:.0%})\n"
    "{p2}: судьи {p2_avg:.1f}/100, голоса зрителей {p2_votes} ({p2_share:.0%})\n\n"
    "Итог с учётом веса судей/зрителей (70/30): {p1} {p1_weighted:.1%} — {p2_weighted:.1%} {p2}\n\n"
    "{winner_line}\n\n"
    "Эло: {p1} {elo1_before}→{elo1_after} ({elo1_delta:+d}), "
    "{p2} {elo2_before}→{elo2_after} ({elo2_delta:+d})"
)
FINALIZE_WINNER_LINE = "🥇 Победитель: <b>{winner}</b>!"
FINALIZE_DRAW_LINE = "🤝 Ничья!"

VOTE_PROMPT = "🗳 За кого болеешь в этом Power Battle?"
VOTE_ACCEPTED = "Голос учтён!"

SEASON_STARTED = "🆕 Начат новый сезон: «{name}»."
SEASON_RESET_DONE = "🔄 Рейтинг сброшен для {count} игроков (частичный откат к базовому значению)."

POLL_QUESTION = "Хотите ли вы турниры Power Battle в нашем чате? 🏆"
POLL_OPTIONS = ["Да, хочу!", "Скорее да", "Не уверен(а)", "Не интересно"]

TOURNAMENT_CREATED = "🏆 Турнир «{name}» создан. Слотов: {slots}. Регистрация: /pb_join_tournament {id}"
TOURNAMENT_ANNOUNCE = (
    "🏆 <b>{name}</b>\n"
    "Вселенная: {universe}\n"
    "Набор участников: {joined}/{slots}\n\n"
    "Записаться: /pb_join_tournament {id}"
)
TOURNAMENT_FULL_ANNOUNCE = "🎉 Набор завершён ({slots}/{slots})! Организатор может запускать турнир: /pb_tournament_start {id}"
TOURNAMENT_NOT_OPEN = "Регистрация в этот турнир уже закрыта."
TOURNAMENT_ALREADY_JOINED = "Ты уже зарегистрирован(а) в этом турнире."
TOURNAMENT_JOINED = "✅ Записал(а) тебя на «{name}» ({joined}/{slots})."
TOURNAMENT_NOT_FULL = "Турнир ещё не набрал участников ({joined}/{slots})."
TOURNAMENT_BRACKET_STARTED = "🏁 Турнир стартовал! Пары 1 раунда:\n{pairs}"
TOURNAMENT_ROUND_ADVANCE = "➡️ Раунд {round} завершён. Пары следующего раунда:\n{pairs}"
TOURNAMENT_CHAMPION = "🏆🏆🏆 Чемпион турнира «{name}»: <b>{champion}</b>! Поздравляем!"
