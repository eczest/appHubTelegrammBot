from pathlib import Path

import yaml

from app.menu_store import MenuStore


def _base_menu(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "title": "AppHub",
                "description": "Категории",
                "image": None,
                "button_rows": [
                    {
                        "buttons": [
                            {"id": "iphone", "text": "iPhone", "url": "https://example.com/1"},
                            {"id": "macbook", "text": "MacBook", "url": "https://example.com/2"},
                        ]
                    }
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_menu_store_falls_back_to_base_and_persists_changes(tmp_path: Path) -> None:
    base = tmp_path / "menu.yaml"
    runtime = tmp_path / "menu.json"
    _base_menu(base)
    store = MenuStore(base, runtime)

    assert store.load().button_count == 2
    added = store.add_button("Связаться", "https://t.me/example")
    assert added.id.startswith("custom_")
    assert runtime.exists()
    assert store.load().button_count == 3

    removed = store.delete_button("iphone")
    assert removed is not None
    assert removed.text == "iPhone"
    assert store.load().button_count == 2


def test_menu_store_delete_unknown_is_noop(tmp_path: Path) -> None:
    base = tmp_path / "menu.yaml"
    _base_menu(base)
    store = MenuStore(base, tmp_path / "menu.json")
    assert store.delete_button("missing") is None
    assert store.load().button_count == 2

