from __future__ import annotations

from datetime import datetime
from html import escape
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.admin_access import AdminRegistry, is_authorized_admin, is_owner
from app.channel_menu import ChannelMenuConfigError, ChannelMenuPublishBlocked
from app.channel_state import load_channel_menu_state
from app.config import Settings, build_channel_message_link
from app.menu_store import MenuStore
from app.services.channel_menu_publisher import (
    ChannelMenuNotModified,
    ChannelMenuPublishError,
    publish_fallback_channel_menu,
    publish_rich_channel_menu,
    send_fallback_preview,
    update_fallback_channel_menu,
)
from app.states import ButtonEditorState, ManagerEditorState
from app.timer_state import (
    TimerState,
    enabled_timer,
    format_interval,
    load_timer_state,
    parse_interval,
    save_timer_state,
)
from app.utils.time import localized_now

logger = logging.getLogger(__name__)
router = Router(name="admin")

CHANNEL_MENU_PATH = "config/channel_menu.yaml"
RUNTIME_MENU_PATH = "data/channel_menu_runtime.json"
CHANNEL_MENU_STATE_PATH = "data/channel_menu_state.json"
ADMIN_REGISTRY_PATH = "data/admin_users.json"
TIMER_STATE_PATH = "data/menu_timer.json"

menu_store = MenuStore(CHANNEL_MENU_PATH, RUNTIME_MENU_PATH)
admin_registry = AdminRegistry(ADMIN_REGISTRY_PATH)


@router.message(Command("test"))
async def preview_menu(message: Message, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    try:
        menu = menu_store.load(require_filled_urls=True)
        await message.answer("Предпросмотр ниже. В канал ничего не отправлено.")
        await send_fallback_preview(message.bot, message.chat.id, menu)
    except (ChannelMenuConfigError, ChannelMenuPublishError) as exc:
        await message.answer(f"Не удалось показать предпросмотр: {exc}")


@router.message(Command("publish_menu"))
@router.message(Command("publish_menu_fallback"))
async def publish_menu(message: Message, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    try:
        menu = menu_store.load(require_filled_urls=True)
        state, link = await publish_fallback_channel_menu(
            message.bot, settings, menu, CHANNEL_MENU_STATE_PATH, _now(settings)
        )
    except ChannelMenuPublishBlocked as exc:
        await message.answer("Меню не опубликовано. Заполните URL: " + ", ".join(exc.button_ids))
        return
    except (ChannelMenuConfigError, ChannelMenuPublishError) as exc:
        await message.answer(f"Меню не опубликовано: {exc}")
        return
    await message.answer(
        "Меню опубликовано.\n"
        f"message_id: <code>{state.message_id}</code>\n"
        f"Ссылка: {link}",
        disable_web_page_preview=True,
    )


@router.message(Command("update_menu"))
async def update_menu(message: Message, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    state = load_channel_menu_state(CHANNEL_MENU_STATE_PATH)
    if state is None:
        await message.answer("Меню ещё не публиковалось. Сначала выполните /publish_menu.")
        return
    try:
        menu = menu_store.load(require_filled_urls=True)
        new_state, link = await update_fallback_channel_menu(
            message.bot, settings, menu, state, CHANNEL_MENU_STATE_PATH, _now(settings)
        )
    except ChannelMenuNotModified as exc:
        await message.answer(str(exc))
        return
    except (ChannelMenuConfigError, ChannelMenuPublishError) as exc:
        await message.answer(f"Меню не обновлено: {exc}")
        return
    await message.answer(
        "Меню обновлено.\n"
        f"message_id: <code>{new_state.message_id}</code>\n"
        f"Ссылка: {link}",
        disable_web_page_preview=True,
    )


@router.message(Command("publish_menu_rich"))
async def publish_menu_rich(message: Message, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    try:
        menu = menu_store.load(require_filled_urls=True)
        state, link = await publish_rich_channel_menu(
            message.bot, settings, menu, CHANNEL_MENU_STATE_PATH, _now(settings)
        )
    except (ChannelMenuConfigError, ChannelMenuPublishError) as exc:
        await message.answer(f"Rich-меню не опубликовано: {exc}")
        return
    await message.answer(
        f"Rich-меню опубликовано.\nmessage_id: <code>{state.message_id}</code>\nСсылка: {link}",
        disable_web_page_preview=True,
    )


@router.message(Command("menu_status"))
async def menu_status(message: Message, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    try:
        menu = menu_store.load()
    except ChannelMenuConfigError as exc:
        await message.answer(f"Ошибка меню: {exc}")
        return
    state = load_channel_menu_state(CHANNEL_MENU_STATE_PATH)
    timer = load_timer_state(TIMER_STATE_PATH)
    lines = [
        f"CHANNEL_ID: <code>{settings.channel_id}</code>",
        f"Кнопок: <code>{menu.button_count}</code>",
        f"Автопубликация: {_timer_summary(timer)}",
    ]
    if state:
        lines.extend(
            [
                f"message_id: <code>{state.message_id}</code>",
                f"Ссылка: {build_channel_message_link(settings.channel_id, state.message_id)}",
                f"Последнее обновление: <code>{state.updated_at}</code>",
            ]
        )
    else:
        lines.append("Опубликованное меню не найдено.")
    await message.answer("\n".join(lines), disable_web_page_preview=True)


@router.message(Command("buttons"))
async def buttons_panel(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    await state.clear()
    await _send_buttons_panel(message)


@router.callback_query(F.data == "buttons:add")
async def add_button_start(callback: CallbackQuery, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    await state.set_state(ButtonEditorState.waiting_for_text)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Отправьте текст новой кнопки. Максимум 64 символа.",
            reply_markup=_cancel_keyboard(),
        )


@router.message(ButtonEditorState.waiting_for_text, F.text)
async def add_button_text(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_message(message, settings):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text or len(text) > 64:
        await message.answer("Текст должен содержать от 1 до 64 символов.")
        return
    await state.update_data(button_text=text)
    await state.set_state(ButtonEditorState.waiting_for_url)
    await message.answer("Теперь отправьте полную ссылку кнопки, начиная с https://")


@router.message(ButtonEditorState.waiting_for_url, F.text)
async def add_button_url(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_message(message, settings):
        await state.clear()
        return
    data = await state.get_data()
    try:
        button = menu_store.add_button(str(data["button_text"]), message.text or "")
    except (ChannelMenuConfigError, KeyError) as exc:
        await message.answer(f"Кнопка не добавлена: {exc}\nОтправьте корректную ссылку.")
        return
    await state.clear()
    await message.answer(f"Кнопка «{escape(button.text)}» добавлена. Проверьте через /test.")


@router.callback_query(F.data == "buttons:delete")
async def delete_button_panel(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    await callback.answer()
    menu = menu_store.load()
    rows = [
        [InlineKeyboardButton(text=f"Удалить: {button.text}", callback_data=f"buttons:rm:{button.id}")]
        for row in menu.button_rows
        for button in row.buttons
    ]
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")])
    if callback.message:
        await callback.message.answer(
            "Выберите кнопку, которую нужно удалить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )


@router.callback_query(F.data.startswith("buttons:rm:"))
async def delete_button(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    button_id = (callback.data or "").removeprefix("buttons:rm:")
    try:
        removed = menu_store.delete_button(button_id)
    except ChannelMenuConfigError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("Кнопка удалена" if removed else "Кнопка уже отсутствует", show_alert=True)
    if callback.message and removed:
        await callback.message.answer(f"Кнопка «{escape(removed.text)}» удалена. Проверьте через /test.")


@router.callback_query(F.data == "buttons:reorder")
async def reorder_buttons_panel(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Меняйте порядок стрелками. После завершения проверьте меню через /test.",
            reply_markup=_reorder_buttons_keyboard(),
        )


@router.callback_query(F.data.startswith("buttons:move:"))
async def move_button(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or parts[3] not in {"up", "down"}:
        await callback.answer("Некорректная команда", show_alert=True)
        return
    moved = menu_store.move_button(parts[2], -1 if parts[3] == "up" else 1)
    await callback.answer("Порядок изменён" if moved else "Дальше переместить нельзя")
    if callback.message and moved:
        await callback.message.edit_reply_markup(reply_markup=_reorder_buttons_keyboard())


@router.message(Command("managers"))
async def managers_panel(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_owner_message(message, settings):
        return
    await state.clear()
    dynamic = sorted(admin_registry.load())
    lines = ["<b>Доступ к управлению ботом</b>", "", "Владельцы из .env:"]
    lines.extend(f"• <code>{user_id}</code>" for user_id in sorted(settings.admin_user_ids))
    lines.append("\nДобавленные менеджеры:")
    lines.extend(f"• <code>{user_id}</code>" for user_id in dynamic)
    if not dynamic:
        lines.append("• нет")
    rows = [[InlineKeyboardButton(text="Добавить менеджера", callback_data="managers:add")]]
    rows.extend(
        [InlineKeyboardButton(text=f"Удалить {user_id}", callback_data=f"managers:rm:{user_id}")]
        for user_id in dynamic
    )
    await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "managers:add")
async def add_manager_start(callback: CallbackQuery, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_owner_callback(callback, settings):
        return
    await state.set_state(ManagerEditorState.waiting_for_id)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Отправьте числовой Telegram ID менеджера. Он может узнать его командой /chatid.",
            reply_markup=_cancel_keyboard(),
        )


@router.message(ManagerEditorState.waiting_for_id, F.text)
async def add_manager_id(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_owner_message(message, settings):
        await state.clear()
        return
    try:
        user_id = int((message.text or "").strip())
        if user_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Нужен положительный числовой Telegram ID.")
        return
    if is_owner(user_id, settings):
        await message.answer("Этот пользователь уже является владельцем.")
    else:
        added = admin_registry.add(user_id)
        await message.answer("Менеджер добавлен." if added else "Этот менеджер уже добавлен.")
    await state.clear()


@router.callback_query(F.data.startswith("managers:rm:"))
async def remove_manager(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_owner_callback(callback, settings):
        return
    user_id = int((callback.data or "0").rsplit(":", 1)[-1])
    removed = admin_registry.remove(user_id)
    await callback.answer("Доступ удалён" if removed else "Менеджер уже отсутствует", show_alert=True)
    if callback.message and removed:
        await callback.message.answer(f"Менеджер <code>{user_id}</code> больше не имеет доступа.")


@router.message(Command("timer"))
async def timer_command(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return
    argument = (command.args or "").strip().lower()
    if argument in {"off", "stop", "выкл"}:
        save_timer_state(TIMER_STATE_PATH, TimerState(False, 0, None))
        await message.answer("Автопубликация отключена.")
        return
    if argument:
        try:
            seconds = parse_interval(argument)
        except ValueError as exc:
            await message.answer(f"Некорректный интервал: {exc}")
            return
        timer = enabled_timer(seconds, _now(settings))
        save_timer_state(TIMER_STATE_PATH, timer)
        await message.answer(f"Автопубликация включена: каждые {format_interval(seconds)}")
        return
    timer = load_timer_state(TIMER_STATE_PATH)
    await message.answer(
        f"<b>Автопубликация меню</b>\n\nТекущее состояние: {_timer_summary(timer)}\n\n"
        "Можно также написать: <code>/timer 30m</code>, <code>/timer 6h</code> или "
        "<code>/timer 1d</code>.",
        reply_markup=_timer_keyboard(),
    )


@router.callback_query(F.data.startswith("timer:set:"))
async def set_timer_callback(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    seconds = int((callback.data or "0").rsplit(":", 1)[-1])
    save_timer_state(TIMER_STATE_PATH, enabled_timer(seconds, _now(settings)))
    await callback.answer(f"Установлено: каждые {format_interval(seconds)}", show_alert=True)


@router.callback_query(F.data == "timer:off")
async def disable_timer_callback(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    save_timer_state(TIMER_STATE_PATH, TimerState(False, 0, None))
    await callback.answer("Автопубликация отключена", show_alert=True)


@router.callback_query(F.data == "admin:cancel")
async def cancel_admin_action(callback: CallbackQuery, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    await state.clear()
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.answer("Действие отменено.")


async def _send_buttons_panel(message: Message) -> None:
    menu = menu_store.load()
    lines = ["<b>Кнопки меню</b>", ""]
    lines.extend(
        f"• {escape(button.text)} — <code>{escape(button.id)}</code>"
        for row in menu.button_rows
        for button in row.buttons
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить кнопку", callback_data="buttons:add")],
            [InlineKeyboardButton(text="Удалить кнопку", callback_data="buttons:delete")],
            [InlineKeyboardButton(text="Изменить порядок", callback_data="buttons:reorder")],
        ]
    )
    await message.answer("\n".join(lines), reply_markup=keyboard)


def _reorder_buttons_keyboard() -> InlineKeyboardMarkup:
    buttons = [button for row in menu_store.load().button_rows for button in row.buttons]
    rows: list[list[InlineKeyboardButton]] = []
    for index, button in enumerate(buttons):
        row = [InlineKeyboardButton(text=button.text, callback_data="buttons:noop")]
        if index > 0:
            row.append(
                InlineKeyboardButton(text="⬆️", callback_data=f"buttons:move:{button.id}:up")
            )
        if index < len(buttons) - 1:
            row.append(
                InlineKeyboardButton(text="⬇️", callback_data=f"buttons:move:{button.id}:down")
            )
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Готово", callback_data="admin:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "buttons:noop")
async def button_reorder_noop(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return
    await callback.answer("Используйте стрелки справа")


def _timer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 час", callback_data="timer:set:3600"),
                InlineKeyboardButton(text="3 часа", callback_data="timer:set:10800"),
            ],
            [
                InlineKeyboardButton(text="6 часов", callback_data="timer:set:21600"),
                InlineKeyboardButton(text="12 часов", callback_data="timer:set:43200"),
            ],
            [InlineKeyboardButton(text="24 часа", callback_data="timer:set:86400")],
            [InlineKeyboardButton(text="Отключить", callback_data="timer:off")],
        ]
    )


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")]]
    )


def _timer_summary(timer: TimerState) -> str:
    if not timer.enabled:
        return "выключена"
    next_run = timer.next_run_at or "не назначено"
    return f"каждые {format_interval(timer.interval_seconds)}, следующий запуск <code>{next_run}</code>"


async def _ensure_admin_message(message: Message, settings: Settings) -> bool:
    user_id = message.from_user.id if message.from_user else None
    if not is_authorized_admin(user_id, settings, admin_registry):
        logger.warning("Rejected admin command from user_id=%s", user_id)
        await message.answer("Нет доступа к этой команде.")
        return False
    if message.chat.type != "private":
        await message.answer("Административные команды выполняются в личном чате с ботом.")
        return False
    return True


async def _ensure_owner_message(message: Message, settings: Settings) -> bool:
    if not is_owner(message.from_user.id if message.from_user else None, settings):
        await message.answer("Только владелец может управлять менеджерами.")
        return False
    if message.chat.type != "private":
        await message.answer("Административные команды выполняются в личном чате с ботом.")
        return False
    return True


async def _ensure_admin_callback(callback: CallbackQuery, settings: Settings) -> bool:
    if not is_authorized_admin(callback.from_user.id, settings, admin_registry):
        await callback.answer("Нет доступа", show_alert=True)
        return False
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Откройте личный чат с ботом", show_alert=True)
        return False
    return True


async def _ensure_owner_callback(callback: CallbackQuery, settings: Settings) -> bool:
    if not is_owner(callback.from_user.id, settings):
        await callback.answer("Только владелец может управлять менеджерами", show_alert=True)
        return False
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Откройте личный чат с ботом", show_alert=True)
        return False
    return True


def _now(settings: Settings) -> datetime:
    return localized_now(settings.timezone)
