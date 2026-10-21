from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from app.channel_menu import (
    ChannelMenu,
    ChannelMenuButton,
    ChannelMenuConfigError,
    ChannelMenuRow,
    load_channel_menu,
    parse_channel_menu,
)


class MenuStore:
    def __init__(self, base_path: str | Path, runtime_path: str | Path) -> None:
        self.base_path = Path(base_path)
        self.runtime_path = Path(runtime_path)

    def load(self, *, require_filled_urls: bool = False) -> ChannelMenu:
        if not self.runtime_path.exists():
            return load_channel_menu(self.base_path, require_filled_urls=require_filled_urls)
        try:
            raw = json.loads(self.runtime_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChannelMenuConfigError(f"Не удалось прочитать сохранённое меню: {exc}") from exc
        return parse_channel_menu(raw, require_filled_urls=require_filled_urls)

    def save(self, menu: ChannelMenu) -> None:
        raw = asdict(menu)
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.runtime_path.with_name(f".{self.runtime_path.name}.tmp")
        tmp_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self.runtime_path)

    def add_button(self, text: str, url: str) -> ChannelMenuButton:
        menu = self.load()
        button = ChannelMenuButton(id=f"custom_{uuid4().hex[:10]}", text=text.strip(), url=url.strip())
        candidate = ChannelMenu(
            title=menu.title,
            description=menu.description,
            image=menu.image,
            button_rows=(*menu.button_rows, ChannelMenuRow(buttons=(button,))),
        )
        validated = parse_channel_menu(json.loads(json.dumps(asdict(candidate))))
        self.save(validated)
        return button

    def delete_button(self, button_id: str) -> ChannelMenuButton | None:
        menu = self.load()
        removed: ChannelMenuButton | None = None
        rows: list[ChannelMenuRow] = []
        for row in menu.button_rows:
            kept: list[ChannelMenuButton] = []
            for button in row.buttons:
                if button.id == button_id:
                    removed = button
                else:
                    kept.append(button)
            if kept:
                rows.append(ChannelMenuRow(buttons=tuple(kept)))
        if removed is None:
            return None
        if not rows:
            raise ChannelMenuConfigError("Нельзя удалить последнюю кнопку меню")
        updated = ChannelMenu(menu.title, menu.description, menu.image, tuple(rows))
        self.save(updated)
        return removed

    def move_button(self, button_id: str, direction: int) -> bool:
        if direction not in {-1, 1}:
            raise ValueError("direction must be -1 or 1")

        menu = self.load()
        row_sizes = [len(row.buttons) for row in menu.button_rows]
        buttons = [button for row in menu.button_rows for button in row.buttons]
        try:
            current_index = next(index for index, button in enumerate(buttons) if button.id == button_id)
        except StopIteration:
            return False

        target_index = current_index + direction
        if target_index < 0 or target_index >= len(buttons):
            return False
        buttons[current_index], buttons[target_index] = buttons[target_index], buttons[current_index]

        rows: list[ChannelMenuRow] = []
        offset = 0
        for size in row_sizes:
            rows.append(ChannelMenuRow(buttons=tuple(buttons[offset : offset + size])))
            offset += size
        self.save(ChannelMenu(menu.title, menu.description, menu.image, tuple(rows)))
        return True

