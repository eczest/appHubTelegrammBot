from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings


class AdminRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> frozenset[int]:
        if not self.path.exists():
            return frozenset()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        values = raw.get("admin_user_ids", []) if isinstance(raw, dict) else []
        return frozenset(int(value) for value in values if int(value) > 0)

    def save(self, user_ids: set[int] | frozenset[int]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f".{self.path.name}.tmp")
        tmp_path.write_text(
            json.dumps({"admin_user_ids": sorted(user_ids)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def add(self, user_id: int) -> bool:
        current = set(self.load())
        before = len(current)
        current.add(user_id)
        self.save(current)
        return len(current) != before

    def remove(self, user_id: int) -> bool:
        current = set(self.load())
        if user_id not in current:
            return False
        current.remove(user_id)
        self.save(current)
        return True


def is_owner(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id in settings.admin_user_ids


def is_authorized_admin(user_id: int | None, settings: Settings, registry: AdminRegistry) -> bool:
    return is_owner(user_id, settings) or (user_id is not None and user_id in registry.load())

