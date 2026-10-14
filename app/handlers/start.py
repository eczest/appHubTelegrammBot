from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.admin_access import AdminRegistry, is_authorized_admin
from app.config import Settings
from app.keyboards.callbacks import NAV_MAIN
from app.states import OrderState, QuestionState

router = Router(name="start")
logger = logging.getLogger(__name__)
admin_registry = AdminRegistry("data/admin_users.json")
ORDER_PROMPT = (
    "Напишите одним сообщением, какой товар хотите приобрести, его цвет и объём памяти. "
    "Мы передадим заявку менеджеру."
)
CONTACT_PROMPT = "Напишите ваш вопрос одним сообщением, и мы передадим его менеджеру."


def resolve_start_action(args: str | None) -> str:
    if not args:
        return "main"
    first_arg = args.split(maxsplit=1)[0].strip().lower()
    if first_arg in {"order", "contact"}:
        return first_arg
    return "main"

ADMIN_HELP_TEXT = (
    "<b>Управление меню AppHub</b>\n\n"
    "<b>/test</b> — показать точный предпросмотр в личном чате, не публикуя его.\n"
    "<b>/publish_menu</b> — опубликовать новое меню в канале.\n"
    "<b>/update_menu</b> — обновить последнее опубликованное меню.\n"
    "<b>/buttons</b> — добавить или удалить кнопки меню.\n"
    "<b>/timer</b> — настроить автоматическую публикацию.\n"
    "<b>/timer 30m</b>, <b>/timer 6h</b>, <b>/timer 1d</b> — установить свой интервал.\n"
    "<b>/timer off</b> — отключить автоматическую публикацию.\n"
    "<b>/menu_status</b> — посмотреть состояние меню и таймера.\n"
    "<b>/managers</b> — добавить или удалить менеджеров; доступно только владельцу.\n"
    "<b>/info</b> — снова показать эту инструкцию.\n\n"
    "Рекомендуемый порядок: внесите изменения через <b>/buttons</b>, проверьте их "
    "командой <b>/test</b>, затем используйте <b>/update_menu</b> или <b>/publish_menu</b>."
)

PRIVATE_BOT_TEXT = "Этот бот используется для управления меню AppHub."


@router.message(CommandStart())
async def handle_start(
    message: Message,
    command: CommandObject,
    settings: Settings,
    state: FSMContext,
) -> None:
    logger.info(
        "Received /start from user_id=%s chat_id=%s chat_type=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
        message.chat.type,
    )
    if message.chat.type != "private":
        return
    action = resolve_start_action(command.args)
    if action == "order":
        await state.set_state(OrderState.waiting_for_order)
        await message.answer(ORDER_PROMPT)
        return
    if action == "contact":
        await state.set_state(QuestionState.waiting_for_question)
        await message.answer(CONTACT_PROMPT)
        return
    if is_authorized_admin(
        message.from_user.id if message.from_user else None, settings, admin_registry
    ):
        await message.answer(ADMIN_HELP_TEXT)
    else:
        await message.answer(PRIVATE_BOT_TEXT)


@router.message(Command("chatid"))
async def handle_chat_id(message: Message) -> None:
    logger.info("Received /chatid in chat_id=%s thread_id=%s", message.chat.id, message.message_thread_id)
    lines = [f"chat.id: <code>{message.chat.id}</code>"]
    if message.message_thread_id is not None:
        lines.append(f"message_thread_id: <code>{message.message_thread_id}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("info"))
async def handle_info(message: Message, settings: Settings) -> None:
    if message.chat.type != "private":
        return
    if is_authorized_admin(
        message.from_user.id if message.from_user else None, settings, admin_registry
    ):
        await message.answer(ADMIN_HELP_TEXT)
    else:
        await message.answer(PRIVATE_BOT_TEXT)


@router.callback_query(lambda callback: callback.data == NAV_MAIN)
async def handle_back_to_main(callback: CallbackQuery, settings: Settings) -> None:
    await callback.answer()
    if callback.message:
        text = (
            ADMIN_HELP_TEXT
            if is_authorized_admin(
                callback.from_user.id if callback.from_user else None, settings, admin_registry
            )
            else PRIVATE_BOT_TEXT
        )
        await callback.message.answer(text)


@router.message(StateFilter(None))
async def handle_unknown_message(message: Message, settings: Settings) -> None:
    logger.info(
        "Received unsupported message from user_id=%s chat_id=%s chat_type=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
        message.chat.type,
    )
    if message.chat.type != "private":
        return
    text = (
        ADMIN_HELP_TEXT
        if is_authorized_admin(
            message.from_user.id if message.from_user else None, settings, admin_registry
        )
        else PRIVATE_BOT_TEXT
    )
    await message.answer(text)
