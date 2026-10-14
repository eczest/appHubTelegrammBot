from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)


async def answer_with_optional_photo(
    message: Message,
    image_path: str | None,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if image_path:
        path = Path(image_path)
        if path.is_file():
            await message.answer_photo(
                FSInputFile(path),
                caption=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return
        logger.warning("Image is missing: %s", path)

    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
