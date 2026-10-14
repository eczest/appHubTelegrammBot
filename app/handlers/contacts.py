from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Settings, StoreContent
from app.keyboards.callbacks import MENU_CONTACTS
from app.keyboards.inline import contacts_keyboard
from app.services.media import answer_with_optional_photo
from app.utils.formatting import format_contacts_html

router = Router(name="contacts")

CONTACTS_IMAGE = "assets/categories/contacts.png"


@router.callback_query(F.data == MENU_CONTACTS)
async def show_contacts(callback: CallbackQuery, content: StoreContent, settings: Settings) -> None:
    await callback.answer()
    if callback.message:
        await answer_with_optional_photo(
            callback.message,
            CONTACTS_IMAGE,
            format_contacts_html(content),
            reply_markup=contacts_keyboard(settings.channel_url),
        )
