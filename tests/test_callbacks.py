import pytest

from app.keyboards.callbacks import (
    make_category_callback,
    make_menu_callback,
    make_model_callback,
    parse_callback,
)


def test_make_callback_data() -> None:
    assert make_menu_callback("catalog") == "menu:catalog"
    assert make_category_callback("iphone") == "cat:iphone"
    assert make_model_callback("iphone", "iphone_17_pro") == "model:iphone:iphone_17_pro"


def test_parse_callback_data() -> None:
    assert parse_callback("menu:contacts").action == "contacts"
    parsed = parse_callback("model:iphone:iphone_17_pro")
    assert parsed.kind == "model"
    assert parsed.category_id == "iphone"
    assert parsed.model_id == "iphone_17_pro"


def test_parse_unknown_callback() -> None:
    with pytest.raises(ValueError):
        parse_callback("unknown")
