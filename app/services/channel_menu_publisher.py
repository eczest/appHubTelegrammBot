from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, InputMediaPhoto, LinkPreviewOptions, Message

from app.channel_menu import (
    ChannelMenu,
    build_fallback_keyboard,
    build_rich_message,
    render_fallback_text,
)
from app.channel_state import ChannelMenuState, new_channel_menu_state, save_channel_menu_state
from app.config import Settings, build_channel_message_link

logger = logging.getLogger(__name__)


class ChannelMenuPublishError(RuntimeError):
    """Raised when channel menu cannot be published or updated."""


class ChannelMenuNotModified(ChannelMenuPublishError):
    """Raised when Telegram reports that an update contains no changes."""


async def send_fallback_preview(bot: Bot, chat_id: int, menu: ChannelMenu) -> Message:
    text = render_fallback_text(menu)
    keyboard = build_fallback_keyboard(menu)
    try:
        image_path = Path(menu.image) if menu.image else None
        if image_path and image_path.is_file():
            return await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(image_path),
                reply_markup=keyboard,
            )
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
            link_preview_options=disabled_link_preview_options(),
        )
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while sending menu preview")
        raise ChannelMenuPublishError(_human_telegram_error(exc)) from exc


async def publish_rich_channel_menu(
    bot: Bot,
    settings: Settings,
    menu: ChannelMenu,
    state_path: str | Path,
    now: datetime,
) -> tuple[ChannelMenuState, str]:
    await _ensure_channel_access(bot, settings)
    try:
        sent = await bot.send_rich_message(
            chat_id=settings.channel_id,
            rich_message=build_rich_message(menu),
        )
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while publishing rich channel menu")
        raise ChannelMenuPublishError(_human_telegram_error(exc)) from exc

    state = new_channel_menu_state(sent.message_id, now)
    save_channel_menu_state(state_path, state)
    return state, build_channel_message_link(settings.channel_id, sent.message_id)


async def update_rich_channel_menu(
    bot: Bot,
    settings: Settings,
    menu: ChannelMenu,
    state: ChannelMenuState,
    state_path: str | Path,
    now: datetime,
) -> tuple[ChannelMenuState, str]:
    await _ensure_channel_access(bot, settings)
    try:
        await bot.edit_message_text(
            chat_id=settings.channel_id,
            message_id=state.message_id,
            rich_message=build_rich_message(menu),
            link_preview_options=disabled_link_preview_options(),
        )
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while updating rich channel menu")
        if "message is not modified" in str(exc).lower():
            raise ChannelMenuNotModified(_human_telegram_error(exc)) from exc
        raise ChannelMenuPublishError(_human_telegram_error(exc)) from exc

    new_state = new_channel_menu_state(state.message_id, now)
    save_channel_menu_state(state_path, new_state)
    return new_state, build_channel_message_link(settings.channel_id, state.message_id)


async def update_fallback_channel_menu(
    bot: Bot,
    settings: Settings,
    menu: ChannelMenu,
    state: ChannelMenuState,
    state_path: str | Path,
    now: datetime,
) -> tuple[ChannelMenuState, str]:
    await _ensure_channel_access(bot, settings)
    text = render_fallback_text(menu)
    keyboard = build_fallback_keyboard(menu)
    try:
        image_path = Path(menu.image) if menu.image else None
        if image_path and image_path.is_file():
            await bot.edit_message_media(
                chat_id=settings.channel_id,
                message_id=state.message_id,
                media=InputMediaPhoto(media=FSInputFile(image_path)),
                reply_markup=keyboard,
            )
        else:
            await bot.edit_message_text(
                chat_id=settings.channel_id,
                message_id=state.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                link_preview_options=disabled_link_preview_options(),
            )
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while updating compatible channel menu")
        if "message is not modified" in str(exc).lower():
            raise ChannelMenuNotModified(_human_telegram_error(exc)) from exc
        raise ChannelMenuPublishError(_human_telegram_error(exc)) from exc

    new_state = new_channel_menu_state(state.message_id, now)
    save_channel_menu_state(state_path, new_state)
    return new_state, build_channel_message_link(settings.channel_id, state.message_id)


async def publish_fallback_channel_menu(
    bot: Bot,
    settings: Settings,
    menu: ChannelMenu,
    state_path: str | Path,
    now: datetime,
) -> tuple[ChannelMenuState, str]:
    await _ensure_channel_access(bot, settings)
    text = render_fallback_text(menu)
    keyboard = build_fallback_keyboard(menu)
    try:
        image_path = Path(menu.image) if menu.image else None
        if image_path and image_path.is_file():
            sent: Message = await bot.send_photo(
                chat_id=settings.channel_id,
                photo=FSInputFile(image_path),
                reply_markup=keyboard,
            )
        else:
            sent = await bot.send_message(
                chat_id=settings.channel_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                link_preview_options=disabled_link_preview_options(),
            )
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while publishing fallback channel menu")
        raise ChannelMenuPublishError(_human_telegram_error(exc)) from exc

    state = new_channel_menu_state(sent.message_id, now)
    save_channel_menu_state(state_path, state)
    return state, build_channel_message_link(settings.channel_id, sent.message_id)


def disabled_link_preview_options() -> LinkPreviewOptions:
    return LinkPreviewOptions(is_disabled=True)


async def _ensure_channel_access(bot: Bot, settings: Settings) -> None:
    try:
        await bot.get_chat(settings.channel_id)
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while checking channel access")
        raise ChannelMenuPublishError(_human_telegram_error(exc)) from exc


def _human_telegram_error(exc: TelegramAPIError) -> str:
    text = str(exc)
    lowered = text.lower()
    if "message is not modified" in lowered:
        return "Изменений нет: сообщение уже содержит эту фотографию и эти кнопки."
    if "not enough rights" in lowered or "administrator" in lowered:
        return "У бота недостаточно прав в канале. Добавьте бота администратором канала."
    if "chat not found" in lowered:
        return "Канал не найден. Проверьте CHANNEL_ID и что бот добавлен в канал."
    if "rich" in lowered:
        return "Telegram не принял Rich Message. Проверьте поддержку Rich Message API и используйте /publish_menu_fallback при необходимости."
    return "Telegram API не принял запрос. Подробности записаны в лог."
