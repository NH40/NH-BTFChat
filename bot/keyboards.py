from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить канал", callback_data="add_channel")
    kb.button(text="📋 Мои правила пересылки", callback_data="list_subs")
    kb.button(text="❓ Помощь", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


def target_chat_choice_kb(channel_id: int, target_chats) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for tc in target_chats:
        kb.button(
            text=tc.title or str(tc.tg_chat_id),
            callback_data=f"pick_chat:{channel_id}:{tc.id}",
        )
    kb.button(text="➕ Новый чат", callback_data=f"new_chat:{channel_id}")
    kb.adjust(1)
    return kb.as_markup()


def subs_list_kb(subs) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for sub in subs:
        channel_label = sub.channel.title or sub.channel.username or str(sub.channel.tg_chat_id)
        chat_label = sub.target_chat.title or str(sub.target_chat.tg_chat_id)
        kb.button(text=f"🗑 {channel_label} → {chat_label}", callback_data=f"del_sub:{sub.id}")
    kb.adjust(1)
    return kb.as_markup()
