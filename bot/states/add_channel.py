from aiogram.fsm.state import State, StatesGroup


class AddChannel(StatesGroup):
    waiting_username = State()
