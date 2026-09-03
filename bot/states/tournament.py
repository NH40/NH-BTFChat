from aiogram.fsm.state import State, StatesGroup


class JudgeScoring(StatesGroup):
    p1_evidence = State()
    p1_argumentation = State()
    p1_scaling = State()
    p1_defense = State()
    p1_attack = State()
    p1_math = State()
    p1_structure = State()
    p2_evidence = State()
    p2_argumentation = State()
    p2_scaling = State()
    p2_defense = State()
    p2_attack = State()
    p2_math = State()
    p2_structure = State()
