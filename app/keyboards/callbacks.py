from __future__ import annotations

from dataclasses import dataclass

MAX_CALLBACK_DATA = 64

MENU_CATALOG = "menu:catalog"
MENU_CONTACTS = "menu:contacts"
MENU_QUESTION = "menu:question"
MENU_ORDER = "menu:order"
NAV_MAIN = "nav:main"
NAV_CATEGORIES = "nav:categories"
NAV_CANCEL = "nav:cancel"


@dataclass(frozen=True)
class ParsedCallback:
    kind: str
    action: str | None = None
    category_id: str | None = None
    model_id: str | None = None


def make_menu_callback(action: str) -> str:
    return _ensure_length(f"menu:{action}")


def make_nav_callback(action: str) -> str:
    return _ensure_length(f"nav:{action}")


def make_category_callback(category_id: str) -> str:
    return _ensure_length(f"cat:{category_id}")


def make_model_callback(category_id: str, model_id: str) -> str:
    return _ensure_length(f"model:{category_id}:{model_id}")


def parse_callback(data: str) -> ParsedCallback:
    parts = data.split(":")
    if len(parts) == 2 and parts[0] in {"menu", "nav"}:
        return ParsedCallback(kind=parts[0], action=parts[1])
    if len(parts) == 2 and parts[0] == "cat":
        return ParsedCallback(kind="cat", category_id=parts[1])
    if len(parts) == 3 and parts[0] == "model":
        return ParsedCallback(kind="model", category_id=parts[1], model_id=parts[2])
    raise ValueError(f"Неизвестный callback_data: {data}")


def _ensure_length(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_CALLBACK_DATA:
        raise ValueError(f"callback_data длиннее {MAX_CALLBACK_DATA} байт: {value}")
    return value
