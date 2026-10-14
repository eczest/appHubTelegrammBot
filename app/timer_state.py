from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import re


MIN_INTERVAL_SECONDS = 5 * 60
MAX_INTERVAL_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class TimerState:
    enabled: bool
    interval_seconds: int
    next_run_at: str | None


def parse_interval(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+)\s*([mhdмчд])\s*", value.lower())
    if not match:
        raise ValueError("Используйте формат 30m, 6h или 1d")
    amount = int(match.group(1))
    unit = match.group(2)
    multiplier = 60 if unit in {"m", "м"} else 3600 if unit in {"h", "ч"} else 86400
    seconds = amount * multiplier
    if seconds < MIN_INTERVAL_SECONDS or seconds > MAX_INTERVAL_SECONDS:
        raise ValueError("Интервал должен быть от 5 минут до 30 дней")
    return seconds


def load_timer_state(path: str | Path) -> TimerState:
    state_path = Path(path)
    if not state_path.exists():
        return TimerState(enabled=False, interval_seconds=0, next_run_at=None)
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    return TimerState(
        enabled=bool(raw.get("enabled", False)),
        interval_seconds=int(raw.get("interval_seconds", 0)),
        next_run_at=str(raw["next_run_at"]) if raw.get("next_run_at") else None,
    )


def save_timer_state(path: str | Path, state: TimerState) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_name(f".{state_path.name}.tmp")
    tmp_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(state_path)


def enabled_timer(interval_seconds: int, now: datetime) -> TimerState:
    return TimerState(
        enabled=True,
        interval_seconds=interval_seconds,
        next_run_at=(now + timedelta(seconds=interval_seconds)).isoformat(timespec="seconds"),
    )


def next_timer_run(state: TimerState, now: datetime) -> TimerState:
    return enabled_timer(state.interval_seconds, now)


def format_interval(seconds: int) -> str:
    if seconds % 86400 == 0:
        return f"{seconds // 86400} дн."
    if seconds % 3600 == 0:
        return f"{seconds // 3600} ч."
    return f"{seconds // 60} мин."

