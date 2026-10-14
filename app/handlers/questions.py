from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.keyboards.callbacks import MENU_ORDER, MENU_QUESTION, NAV_CANCEL
from app.keyboards.inline import cancel_keyboard, main_menu_keyboard
from app.services.manager_notifications import (
    ManagerNotificationError,
    send_order_text,
    send_question_media,
    send_question_text,
)
from app.states import OrderState, QuestionState
from app.handlers.start import CONTACT_PROMPT, ORDER_PROMPT

logger = logging.getLogger(__name__)
router = Router(name="questions")


@router.callback_query(F.data == MENU_QUESTION)
async def ask_question(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(QuestionState.waiting_for_question)
    if callback.message:
        await callback.message.answer(CONTACT_PROMPT, reply_markup=cancel_keyboard())


@router.callback_query(F.data == MENU_ORDER)
async def ask_order(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OrderState.waiting_for_order)
    if callback.message:
        await callback.message.answer(ORDER_PROMPT, reply_markup=cancel_keyboard())


@router.callback_query(F.data == NAV_CANCEL)
async def cancel_question(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.answer(
            "Главное меню",
            reply_markup=main_menu_keyboard(settings.channel_url),
        )


@router.message(OrderState.waiting_for_order, F.text)
async def handle_order_text(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить отправителя. Пожалуйста, попробуйте ещё раз.")
        return
    try:
        await send_order_text(message.bot, settings, message.from_user, message.text or "")
    except ManagerNotificationError:
        logger.exception("Failed to send user order to managers")
        await message.answer("Не удалось передать заявку менеджеру. Пожалуйста, попробуйте ещё раз немного позже.")
        return

    await state.clear()
    await message.answer("Спасибо! Заявка передана менеджеру 💗")


@router.message(OrderState.waiting_for_order)
async def handle_unsupported_order(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте заявку одним текстовым сообщением.")


@router.message(QuestionState.waiting_for_question, F.text)
async def handle_question_text(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить отправителя. Пожалуйста, попробуйте ещё раз.")
        return
    try:
        await send_question_text(message.bot, settings, message.from_user, message.text or "")
    except ManagerNotificationError:
        logger.exception("Failed to send user question to managers")
        await message.answer("Не удалось передать вопрос менеджеру. Пожалуйста, попробуйте ещё раз немного позже.")
        return

    await state.clear()
    await message.answer("Спасибо! Ваш вопрос передан менеджеру 💗")


@router.message(QuestionState.waiting_for_question, F.photo | F.document)
async def handle_question_media(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.media_group_id:
        await message.answer("Пожалуйста, отправьте текст, одну фотографию или один документ.")
        return

    try:
        await send_question_media(message.bot, settings, message)
    except ManagerNotificationError:
        logger.exception("Failed to send user media question to managers")
        await message.answer("Не удалось передать вопрос менеджеру. Пожалуйста, попробуйте ещё раз немного позже.")
        return

    await state.clear()
    await message.answer("Спасибо! Ваш вопрос передан менеджеру 💗")


@router.message(QuestionState.waiting_for_question)
async def handle_unsupported_question(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте вопрос текстом, одной фотографией или одним документом.")
