from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path


@dataclass(frozen=True)
class ChannelMenuState:
    message_id: int
    updated_at: str


def load_channel_menu_state(path: str | Path) -> ChannelMenuState | None:
    state_path = Path(path)
    if not state_path.exists():
        return None
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    return ChannelMenuState(message_id=int(raw["message_id"]), updated_at=str(raw["updated_at"]))


def save_channel_menu_state(path: str | Path, state: ChannelMenuState) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_name(f".{state_path.name}.tmp")
    tmp_path.write_text(
        json.dumps(
            {"message_id": state.message_id, "updated_at": state.updated_at},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(state_path)


def new_channel_menu_state(message_id: int, now: datetime) -> ChannelMenuState:
    return ChannelMenuState(message_id=message_id, updated_at=now.isoformat(timespec="seconds"))
