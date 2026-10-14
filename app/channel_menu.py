from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputRichBlockButtons,
    InputRichBlockParagraph,
    InputRichBlockPhoto,
    InputRichBlockSectionHeading,
    InputRichMessage,
    RichMessageButton,
)


class ChannelMenuConfigError(ValueError):
    """Raised when channel_menu.yaml contains invalid data."""


class ChannelMenuPublishBlocked(ChannelMenuConfigError):
    def __init__(self, button_ids: list[str]) -> None:
        self.button_ids = button_ids
        super().__init__("Не заполнены URL кнопок: " + ", ".join(button_ids))


@dataclass(frozen=True)
class ChannelMenuButton:
    id: str
    text: str
    url: str


@dataclass(frozen=True)
class ChannelMenuRow:
    buttons: tuple[ChannelMenuButton, ...]


@dataclass(frozen=True)
class ChannelMenu:
    title: str
    description: str
    image: str | None
    button_rows: tuple[ChannelMenuRow, ...]

    @property
    def button_count(self) -> int:
        return sum(len(row.buttons) for row in self.button_rows)


def load_channel_menu(path: str | Path, *, require_filled_urls: bool = False) -> ChannelMenu:
    menu_path = Path(path)
    try:
        raw = yaml.safe_load(menu_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ChannelMenuConfigError(f"Не удалось прочитать {menu_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ChannelMenuConfigError(f"Файл {menu_path} содержит ошибку YAML: {exc}") from exc
    return parse_channel_menu(raw, require_filled_urls=require_filled_urls)


def parse_channel_menu(raw: Any, *, require_filled_urls: bool = False) -> ChannelMenu:
    if not isinstance(raw, dict):
        raise ChannelMenuConfigError("channel_menu.yaml должен содержать YAML-объект")

    _reject_unknown(raw, {"title", "description", "image", "button_rows"}, "channel_menu")
    title = _required_string(raw.get("title"), "title")
    description = _required_string(raw.get("description"), "description")
    image = raw.get("image")
    if image is not None and not isinstance(image, str):
        raise ChannelMenuConfigError("image должен быть строкой или пустым")

    rows_raw = raw.get("button_rows")
    if not isinstance(rows_raw, list) or not rows_raw:
        raise ChannelMenuConfigError("button_rows должен быть непустым списком")

    seen_ids: set[str] = set()
    change_me_ids: list[str] = []
    rows: list[ChannelMenuRow] = []
    for row_index, row_raw in enumerate(rows_raw, start=1):
        if not isinstance(row_raw, dict):
            raise ChannelMenuConfigError(f"Строка кнопок #{row_index} должна быть объектом")
        _reject_unknown(row_raw, {"buttons"}, f"button_rows[{row_index}]")

        buttons_raw = row_raw.get("buttons")
        if not isinstance(buttons_raw, list) or not buttons_raw:
            raise ChannelMenuConfigError(f"Строка кнопок #{row_index} должна содержать 1-2 кнопки")
        if len(buttons_raw) > 2:
            raise ChannelMenuConfigError(f"Строка кнопок #{row_index} содержит больше двух кнопок")

        buttons: list[ChannelMenuButton] = []
        for button_index, button_raw in enumerate(buttons_raw, start=1):
            context = f"button_rows[{row_index}].buttons[{button_index}]"
            if not isinstance(button_raw, dict):
                raise ChannelMenuConfigError(f"{context} должен быть объектом")
            _reject_unknown(button_raw, {"id", "text", "url"}, context)

            button_id = _required_string(button_raw.get("id"), f"{context}.id")
            text = _required_string(button_raw.get("text"), f"{context}.text")
            url = _required_string(button_raw.get("url"), f"{context}.url")

            if button_id in seen_ids:
                raise ChannelMenuConfigError(f"Повторяющийся ID кнопки: {button_id}")
            seen_ids.add(button_id)
            if "CHANGE_ME" in url:
                change_me_ids.append(button_id)
            if len(text) > 64:
                raise ChannelMenuConfigError(f"Текст кнопки {button_id} длиннее 64 символов")
            if not _is_valid_url(url):
                raise ChannelMenuConfigError(f"Некорректный URL у кнопки {button_id}: {url}")

            buttons.append(ChannelMenuButton(id=button_id, text=text, url=url))
        rows.append(ChannelMenuRow(buttons=tuple(buttons)))

    if require_filled_urls and change_me_ids:
        raise ChannelMenuPublishBlocked(change_me_ids)

    return ChannelMenu(
        title=title,
        description=description,
        image=image.strip() if isinstance(image, str) and image.strip() else None,
        button_rows=tuple(rows),
    )


def build_rich_message(menu: ChannelMenu) -> InputRichMessage:
    blocks: list[Any] = []
    if menu.image and Path(menu.image).is_file():
        blocks.append(InputRichBlockPhoto(photo=InputMediaPhoto(media=FSInputFile(menu.image))))

    blocks.extend(
        [
            InputRichBlockSectionHeading(text=menu.title, size=2),
            InputRichBlockParagraph(text=menu.description),
        ]
    )
    for row in menu.button_rows:
        blocks.append(
            InputRichBlockButtons(
                buttons=[
                    RichMessageButton(text=button.text, url=button.url, style="primary")
                    for button in row.buttons
                ],
                align="center",
            )
        )
    return InputRichMessage(blocks=blocks, skip_entity_detection=True)


def build_fallback_keyboard(menu: ChannelMenu) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button.text, url=button.url) for button in row.buttons]
            for row in menu.button_rows
        ]
    )


def render_fallback_text(menu: ChannelMenu) -> str:
    return f"<b>{escape(menu.title, quote=False)}</b>\n\n{escape(menu.description, quote=False)}"


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChannelMenuConfigError(f"{field} должен быть непустой строкой")
    return value.strip()


def _reject_unknown(raw: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ChannelMenuConfigError(f"{context}: неизвестные поля: {', '.join(sorted(unknown))}")


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http", "tg"}:
        return False
    if parsed.scheme in {"https", "http"}:
        return bool(parsed.netloc)
    return bool(parsed.scheme and parsed.path)
