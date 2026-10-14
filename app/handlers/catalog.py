from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.catalog import Catalog
from app.config import Settings
from app.keyboards.callbacks import MENU_CATALOG, NAV_CATEGORIES, make_category_callback, parse_callback
from app.keyboards.inline import categories_keyboard, models_keyboard
from app.services.manager_notifications import (
    ManagerNotificationError,
    RecentActionGuard,
    send_product_request,
)
from app.services.media import answer_with_optional_photo

logger = logging.getLogger(__name__)
router = Router(name="catalog")

CATALOG_IMAGE = "assets/categories/catalog.png"


@router.callback_query(F.data == MENU_CATALOG)
async def show_categories(callback: CallbackQuery, catalog: Catalog) -> None:
    await callback.answer()
    if callback.message:
        await answer_with_optional_photo(
            callback.message,
            CATALOG_IMAGE,
            "Выберите устройство, которое хотели бы приобрести 💕",
            reply_markup=categories_keyboard(catalog),
        )


@router.callback_query(F.data == NAV_CATEGORIES)
async def back_to_categories(callback: CallbackQuery, catalog: Catalog) -> None:
    await callback.answer()
    if callback.message:
        await answer_with_optional_photo(
            callback.message,
            CATALOG_IMAGE,
            "Выберите устройство, которое хотели бы приобрести 💕",
            reply_markup=categories_keyboard(catalog),
        )


@router.callback_query(F.data.startswith("cat:"))
async def show_models(callback: CallbackQuery, catalog: Catalog) -> None:
    parsed = parse_callback(callback.data or "")
    category = catalog.get_category(parsed.category_id or "")
    if category is None:
        await callback.answer("Категория пока не настроена", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await answer_with_optional_photo(
            callback.message,
            category.image,
            f"<b>{category.name}</b>\n\nВыберите модель {category.name}",
            reply_markup=models_keyboard(category),
        )


@router.callback_query(F.data.startswith("model:"))
async def create_product_request(
    callback: CallbackQuery,
    catalog: Catalog,
    settings: Settings,
    recent_guard: RecentActionGuard,
) -> None:
    parsed = parse_callback(callback.data or "")
    category = catalog.get_category(parsed.category_id or "")
    model = catalog.get_model(parsed.category_id or "", parsed.model_id or "")
    if category is None or model is None:
        await callback.answer("Эта модель уже недоступна", show_alert=True)
        return

    guard_key = f"{callback.from_user.id}:{category.id}:{model.id}"
    if recent_guard.is_duplicate(guard_key):
        await callback.answer("Заявка уже отправлена", show_alert=False)
        return

    await callback.answer()
    logger.info(
        "Product request received: user_id=%s category=%s model=%s",
        callback.from_user.id,
        category.id,
        model.id,
    )
    try:
        await send_product_request(callback.bot, settings, category.name, model.name, callback.from_user)
    except ManagerNotificationError:
        recent_guard.forget(guard_key)
        logger.exception("Failed to send product request to managers")
        if callback.message:
            await callback.message.answer(
                "Не удалось передать заявку менеджеру. Пожалуйста, попробуйте ещё раз немного позже."
            )
        return

    logger.info("Product request sent to managers: user_id=%s", callback.from_user.id)
    if callback.message:
        await callback.message.answer(
            "Отлично, сейчас менеджер освободится и поможет Вам 💗\n\n"
            "Подскажите, какой цвет и объём памяти рассматриваете к покупке?"
        )
