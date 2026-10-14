from datetime import datetime

from app.channel_state import (
    ChannelMenuState,
    load_channel_menu_state,
    new_channel_menu_state,
    save_channel_menu_state,
)


def test_read_and_atomic_save_message_id(tmp_path) -> None:
    state_path = tmp_path / "channel_menu_state.json"
    state = ChannelMenuState(message_id=42, updated_at="2026-09-15T12:00:00+05:00")
    save_channel_menu_state(state_path, state)
    assert load_channel_menu_state(state_path) == state
    assert not (tmp_path / ".channel_menu_state.json.tmp").exists()


def test_new_channel_menu_state() -> None:
    state = new_channel_menu_state(77, datetime(2026, 9, 15, 12, 1, 2))
    assert state.message_id == 77
    assert state.updated_at == "2026-09-15T12:01:02"
