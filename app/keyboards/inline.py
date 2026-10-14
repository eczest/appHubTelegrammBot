from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.catalog import Catalog, Category
from app.keyboards.callbacks import (
    MENU_CATALOG,
    MENU_CONTACTS,
    MENU_QUESTION,
    NAV_CANCEL,
    NAV_CATEGORIES,
    NAV_MAIN,
    make_category_callback,
    make_model_callback,
)


def main_menu_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Посмотреть цены", url=channel_url)],
            [InlineKeyboardButton(text="💬 Связаться с менеджером", callback_data=MENU_QUESTION)],
            [InlineKeyboardButton(text="📍 Контакты", callback_data=MENU_CONTACTS)],
        ]
    )


def categories_keyboard(catalog: Catalog) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=category.name, callback_data=make_category_callback(category.id))]
        for category in catalog.categories
        if category.id not in {"other", "services"}
    ]
    other = catalog.get_category("other")
    services = catalog.get_category("services")
    buttons.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=NAV_MAIN),
            InlineKeyboardButton(
                text=other.name if other else "Другое",
                callback_data=make_category_callback("other"),
            ),
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(
                text=services.name if services else "Услуги и подписки",
                callback_data=make_category_callback("services"),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def models_keyboard(category: Category) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=model.name, callback_data=make_model_callback(category.id, model.id))]
        for model in category.models
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=NAV_CATEGORIES)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def contacts_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Посмотреть цены", url=channel_url)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=NAV_MAIN)],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data=NAV_CANCEL)]]
    )


def manager_profile_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👤 Открыть клиента", url=f"tg://user?id={user_id}")]]
    )
