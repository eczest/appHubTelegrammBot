from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.timer_state import (
    enabled_timer,
    format_interval,
    load_timer_state,
    parse_interval,
    save_timer_state,
)


def test_parse_timer_intervals() -> None:
    assert parse_interval("30m") == 1800
    assert parse_interval("6h") == 21600
    assert parse_interval("1d") == 86400
    assert parse_interval("2ч") == 7200
    with pytest.raises(ValueError):
        parse_interval("4m")
    with pytest.raises(ValueError):
        parse_interval("hour")


def test_timer_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "timer.json"
    now = datetime(2026, 10, 20, 10, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
    state = enabled_timer(21600, now)
    save_timer_state(path, state)
    assert load_timer_state(path) == state
    assert state.next_run_at == "2026-10-20T16:00:00+05:00"
    assert format_interval(state.interval_seconds) == "6 ч."

