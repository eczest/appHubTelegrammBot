from pathlib import Path

import pytest
from aiogram.types import InputRichBlockButtons, InputRichBlockPhoto

from app.channel_menu import (
    ChannelMenuConfigError,
    ChannelMenuPublishBlocked,
    build_fallback_keyboard,
    build_rich_message,
    parse_channel_menu,
)
from app.services.channel_menu_publisher import disabled_link_preview_options


def valid_menu() -> dict:
    return {
        "title": "Добро пожаловать в AppHub! 👋",
        "description": "Выберите интересующую категорию:",
        "image": "assets/channel_menu.jpg",
        "button_rows": [
            {
                "buttons": [
                    {
                        "id": "contact",
                        "text": "📞 Связаться с нами",
                        "url": "https://t.me/AppHub_Store_bot?start=contact",
                    }
                ]
            },
            {
                "buttons": [
                    {"id": "iphone", "text": "📱 iPhone", "url": "https://t.me/c/3976893957/2"},
                    {
                        "id": "macbook",
                        "text": "💻 MacBook",
                        "url": "https://t.me/c/3976893957/3",
                    },
                ]
            },
        ],
    }


def test_load_valid_channel_menu() -> None:
    menu = parse_channel_menu(valid_menu(), require_filled_urls=True)
    assert menu.title.startswith("Добро")
    assert menu.button_count == 3


def test_detect_change_me_before_publish() -> None:
    raw = valid_menu()
    raw["button_rows"][1]["buttons"][1]["url"] = "https://t.me/c/3976893957/CHANGE_ME"
    with pytest.raises(ChannelMenuPublishBlocked) as exc:
        parse_channel_menu(raw, require_filled_urls=True)
    assert exc.value.button_ids == ["macbook"]


def test_duplicate_button_id_raises_error() -> None:
    raw = valid_menu()
    raw["button_rows"][1]["buttons"][1]["id"] = "iphone"
    with pytest.raises(ChannelMenuConfigError, match="Повторяющийся ID кнопки"):
        parse_channel_menu(raw)


def test_invalid_url_raises_error() -> None:
    raw = valid_menu()
    raw["button_rows"][0]["buttons"][0]["url"] = "not-a-url"
    with pytest.raises(ChannelMenuConfigError, match="Некорректный URL"):
        parse_channel_menu(raw)


def test_too_many_buttons_in_row_raises_error() -> None:
    raw = valid_menu()
    raw["button_rows"][1]["buttons"].append(
        {"id": "extra", "text": "Extra", "url": "https://example.com"}
    )
    with pytest.raises(ChannelMenuConfigError, match="больше двух"):
        parse_channel_menu(raw)


def test_build_rich_message_keeps_row_order() -> None:
    rich = build_rich_message(parse_channel_menu(valid_menu()))
    button_blocks = [block for block in rich.blocks if isinstance(block, InputRichBlockButtons)]
    assert [button.text for button in button_blocks[0].buttons] == ["📞 Связаться с нами"]
    assert [button.text for button in button_blocks[1].buttons] == ["📱 iPhone", "💻 MacBook"]


def test_build_rich_message_adds_existing_image(tmp_path: Path) -> None:
    image = tmp_path / "menu.jpg"
    image.write_bytes(b"fake")
    raw = valid_menu()
    raw["image"] = str(image)
    rich = build_rich_message(parse_channel_menu(raw))
    assert isinstance(rich.blocks[0], InputRichBlockPhoto)


def test_fallback_keyboard_and_link_preview() -> None:
    menu = parse_channel_menu(valid_menu())
    keyboard = build_fallback_keyboard(menu)
    assert keyboard.inline_keyboard[1][0].text == "📱 iPhone"
    assert disabled_link_preview_options().is_disabled is True
