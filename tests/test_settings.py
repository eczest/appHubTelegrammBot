import pytest

from app.config import (
    Settings,
    SettingsError,
    build_channel_message_base_link,
    build_channel_message_link,
    is_admin_user,
    parse_admin_user_ids,
)
from app.handlers.start import resolve_start_action


def test_parse_admin_user_ids() -> None:
    assert parse_admin_user_ids("123, 456,123") == frozenset({123, 456})


def test_parse_admin_user_ids_rejects_empty() -> None:
    with pytest.raises(SettingsError):
        parse_admin_user_ids("")


def test_forbid_admin_command_for_unknown_user() -> None:
    settings = Settings(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        manager_chat_id=-1001,
        manager_topic_id=None,
        channel_id=-1003976893957,
        admin_user_ids=frozenset({123}),
        channel_url="https://t.me/c/3976893957",
        timezone="Asia/Yekaterinburg",
        log_level="INFO",
    )
    assert is_admin_user(999, settings) is False
    assert is_admin_user(123, settings) is True


def test_channel_links_for_private_and_public_channels() -> None:
    assert build_channel_message_link(-1003976893957, 2) == "https://t.me/c/3976893957/2"
    assert build_channel_message_base_link("@apphub_store") == "https://t.me/apphub_store"


def test_start_deep_links() -> None:
    assert resolve_start_action("order") == "order"
    assert resolve_start_action("contact") == "contact"
    assert resolve_start_action(None) == "main"
    assert resolve_start_action("unknown") == "main"
