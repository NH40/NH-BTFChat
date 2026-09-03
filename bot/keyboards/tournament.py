from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def ban_phase_kb(match_id: int, characters) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for character in characters:
        kb.button(text=character.name, callback_data=f"pb_ban:{match_id}:{character.id}")
    kb.adjust(2)
    return kb.as_markup()


def vote_kb(match_id: int, player1_id: int, player1_name: str, player2_id: int, player2_name: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🗳 {player1_name}", callback_data=f"pb_vote:{match_id}:{player1_id}")
    kb.button(text=f"🗳 {player2_name}", callback_data=f"pb_vote:{match_id}:{player2_id}")
    kb.adjust(2)
    return kb.as_markup()


def tournament_join_kb(tournament_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Участвовать", callback_data=f"pb_join_t:{tournament_id}")
    return kb.as_markup()


def judges_random_kb(match_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Назначить судей случайно", callback_data=f"pb_judges_random:{match_id}")
    return kb.as_markup()
