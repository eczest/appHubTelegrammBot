from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from app.config import StoreContent


def html_escape(value: Any) -> str:
    return escape(str(value), quote=False)


def format_user_name(user: Any) -> str:
    first_name = (getattr(user, "first_name", "") or "").strip()
    last_name = (getattr(user, "last_name", "") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return html_escape(full_name or "не указано")


def format_username(user: Any) -> str:
    username = (getattr(user, "username", None) or "").strip()
    return html_escape(f"@{username}" if username else "не указан")


def format_profile_link(user_id: int) -> str:
    return f'<a href="tg://user?id={user_id}">Открыть профиль клиента</a>'


def format_product_request_html(category_name: str, model_name: str, user: Any, request_time: datetime) -> str:
    user_id = int(getattr(user, "id"))
    return (
        "🔥 <b>Новая заявка</b>\n\n"
        f"<b>Категория:</b> {html_escape(category_name)} <b>Модель:</b> {html_escape(model_name)}\n\n"
        f"<b>Клиент:</b> {format_user_name(user)} <b>Username:</b> {format_username(user)} "
        f"<b>Telegram ID:</b> <code>{user_id}</code>\n\n"
        f"{format_profile_link(user_id)}\n\n"
        f"<b>Время заявки:</b> {request_time.strftime('%d.%m.%Y %H:%M')}"
    )


def format_question_text_html(user: Any, question: str) -> str:
    user_id = int(getattr(user, "id"))
    return (
        "💬 <b>Вопрос менеджеру</b>\n\n"
        f"<b>Клиент:</b> {format_user_name(user)} <b>Username:</b> {format_username(user)} "
        f"<b>Telegram ID:</b> <code>{user_id}</code>\n\n"
        "<b>Сообщение:</b>\n"
        f"{html_escape(question)}\n\n"
        f"{format_profile_link(user_id)}"
    )


def format_order_text_html(user: Any, order_text: str, request_time: datetime) -> str:
    user_id = int(getattr(user, "id"))
    return (
        "👉 <b>Новая заявка на заказ</b>\n\n"
        f"<b>Клиент:</b> {format_user_name(user)} <b>Username:</b> {format_username(user)} "
        f"<b>Telegram ID:</b> <code>{user_id}</code>\n\n"
        "<b>Заявка:</b>\n"
        f"{html_escape(order_text)}\n\n"
        f"{format_profile_link(user_id)}\n\n"
        f"<b>Время заявки:</b> {request_time.strftime('%d.%m.%Y %H:%M')}"
    )


def format_question_intro_html(user: Any, caption: str | None = None) -> str:
    user_id = int(getattr(user, "id"))
    caption_block = ""
    if caption:
        caption_block = f"\n\n<b>Подпись:</b>\n{html_escape(caption)}"
    return (
        "💬 <b>Вопрос менеджеру</b>\n\n"
        f"<b>Клиент:</b> {format_user_name(user)} <b>Username:</b> {format_username(user)} "
        f"<b>Telegram ID:</b> <code>{user_id}</code>"
        f"{caption_block}\n\n"
        f"{format_profile_link(user_id)}"
    )


def format_contacts_html(content: StoreContent) -> str:
    addresses = "\n".join(f"• {html_escape(address)}" for address in content.addresses)
    return (
        f"<b>{html_escape(content.name)}</b>\n\n"
        f"<b>Город:</b> {html_escape(content.city)}\n\n"
        f"<b>Адреса:</b>\n{addresses}\n\n"
        f"<b>Телефон:</b> {html_escape(content.phone)}\n"
        f"<b>Режим работы:</b> {html_escape(content.working_hours)}"
    )
