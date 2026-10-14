from __future__ import annotations

import logging
import time
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import Message

from app.config import Settings
from app.keyboards.inline import manager_profile_keyboard
from app.utils.formatting import (
    format_order_text_html,
    format_product_request_html,
    format_question_intro_html,
    format_question_text_html,
)
from app.utils.time import localized_now

logger = logging.getLogger(__name__)


class ManagerNotificationError(RuntimeError):
    """Raised when a message cannot be delivered to managers."""


class RecentActionGuard:
    def __init__(self, ttl_seconds: float = 10.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._items: dict[str, float] = {}

    def is_duplicate(self, key: str) -> bool:
        now = time.monotonic()
        self._clear_expired(now)
        expires_at = self._items.get(key)
        if expires_at and expires_at > now:
            return True
        self._items[key] = now + self._ttl_seconds
        return False

    def forget(self, key: str) -> None:
        self._items.pop(key, None)

    def _clear_expired(self, now: float) -> None:
        expired = [key for key, expires_at in self._items.items() if expires_at <= now]
        for key in expired:
            self._items.pop(key, None)


async def send_product_request(
    bot: Bot,
    settings: Settings,
    category_name: str,
    model_name: str,
    user: Any,
) -> None:
    text = format_product_request_html(
        category_name=category_name,
        model_name=model_name,
        user=user,
        request_time=localized_now(settings.timezone),
    )
    await _send_manager_message(bot, settings, text, user_id=user.id)


async def send_question_text(bot: Bot, settings: Settings, user: Any, question: str) -> None:
    text = format_question_text_html(user=user, question=question)
    await _send_manager_message(bot, settings, text, user_id=user.id)


async def send_order_text(bot: Bot, settings: Settings, user: Any, order_text: str) -> None:
    text = format_order_text_html(
        user=user,
        order_text=order_text,
        request_time=localized_now(settings.timezone),
    )
    await _send_manager_message(bot, settings, text, user_id=user.id)


async def send_question_media(bot: Bot, settings: Settings, message: Message) -> None:
    if message.from_user is None:
        raise ManagerNotificationError("Message has no from_user")

    intro = format_question_intro_html(user=message.from_user, caption=message.caption)
    await _send_manager_message(bot, settings, intro, user_id=message.from_user.id)
    try:
        await bot.copy_message(
            chat_id=settings.manager_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=settings.manager_topic_id,
        )
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while copying question media")
        raise ManagerNotificationError("Failed to copy media question to managers") from exc


async def _send_manager_message(bot: Bot, settings: Settings, text: str, user_id: int) -> None:
    try:
        await bot.send_message(
            chat_id=settings.manager_chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=manager_profile_keyboard(user_id),
            message_thread_id=settings.manager_topic_id,
        )
    except TelegramBadRequest as exc:
        logger.warning("Could not send manager URL button, retrying without keyboard: %s", exc)
        try:
            await bot.send_message(
                chat_id=settings.manager_chat_id,
                text=text,
                parse_mode="HTML",
                message_thread_id=settings.manager_topic_id,
            )
        except TelegramAPIError as retry_exc:
            logger.exception("Telegram API error while sending manager notification")
            raise ManagerNotificationError("Failed to send manager notification") from retry_exc
    except TelegramAPIError as exc:
        logger.exception("Telegram API error while sending manager notification")
        raise ManagerNotificationError("Failed to send manager notification") from exc
