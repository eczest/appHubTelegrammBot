import pytest

from app.catalog import CatalogConfigError, parse_catalog


def valid_catalog() -> dict:
    return {
        "categories": [
            {
                "id": "iphone",
                "name": "iPhone",
                "image": "assets/categories/iphone.jpg",
                "models": [
                    {"id": "iphone_17", "name": "iPhone 17"},
                    {"id": "iphone_17_pro", "name": "iPhone 17 Pro"},
                ],
            }
        ]
    }


def test_load_valid_catalog() -> None:
    catalog = parse_catalog(valid_catalog())
    assert len(catalog.categories) == 1
    assert catalog.get_category("iphone").name == "iPhone"
    assert catalog.get_model("iphone", "iphone_17").name == "iPhone 17"


def test_duplicate_category_id_raises_error() -> None:
    raw = valid_catalog()
    raw["categories"].append(raw["categories"][0].copy())
    with pytest.raises(CatalogConfigError, match="Повторяющийся ID категории"):
        parse_catalog(raw)


def test_duplicate_model_id_raises_error() -> None:
    raw = valid_catalog()
    raw["categories"][0]["models"].append({"id": "iphone_17", "name": "Duplicate"})
    with pytest.raises(CatalogConfigError, match="Повторяющийся ID модели"):
        parse_catalog(raw)


def test_category_without_models_raises_error() -> None:
    raw = valid_catalog()
    raw["categories"][0]["models"] = []
    with pytest.raises(CatalogConfigError, match="хотя бы одну модель"):
        parse_catalog(raw)
