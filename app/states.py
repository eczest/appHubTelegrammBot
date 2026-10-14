from aiogram.fsm.state import State, StatesGroup


class QuestionState(StatesGroup):
    waiting_for_question = State()


class OrderState(StatesGroup):
    waiting_for_order = State()


class ButtonEditorState(StatesGroup):
    waiting_for_text = State()
    waiting_for_url = State()


class ManagerEditorState(StatesGroup):
    waiting_for_id = State()
