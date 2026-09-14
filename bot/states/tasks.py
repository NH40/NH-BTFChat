from aiogram.fsm.state import State, StatesGroup


class NewTask(StatesGroup):
    waiting_title = State()
    waiting_custom_deadline = State()
