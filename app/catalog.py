from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Any

import yaml

from app.keyboards.callbacks import MAX_CALLBACK_DATA, make_category_callback, make_model_callback

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class CatalogConfigError(ValueError):
    """Raised when catalog.yaml contains invalid data."""


@dataclass(frozen=True)
class Model:
    id: str
    name: str


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    image: str | None
    models: tuple[Model, ...]


@dataclass(frozen=True)
class Catalog:
    categories: tuple[Category, ...]

    def get_category(self, category_id: str) -> Category | None:
        return next((category for category in self.categories if category.id == category_id), None)

    def get_model(self, category_id: str, model_id: str) -> Model | None:
        category = self.get_category(category_id)
        if category is None:
            return None
        return next((model for model in category.models if model.id == model_id), None)


def load_catalog(path: str | Path) -> Catalog:
    catalog_path = Path(path)
    try:
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogConfigError(f"Не удалось прочитать каталог {catalog_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CatalogConfigError(f"YAML-каталог {catalog_path} содержит ошибку синтаксиса: {exc}") from exc

    catalog = parse_catalog(raw)
    logger.info("Catalog loaded from %s: %s categories", catalog_path, len(catalog.categories))
    return catalog


def parse_catalog(raw: Any) -> Catalog:
    if not isinstance(raw, dict):
        raise CatalogConfigError("catalog.yaml должен содержать YAML-объект верхнего уровня")

    categories_raw = raw.get("categories")
    if not isinstance(categories_raw, list) or not categories_raw:
        raise CatalogConfigError("catalog.yaml должен содержать непустой список categories")

    category_ids: set[str] = set()
    categories: list[Category] = []

    for index, item in enumerate(categories_raw, start=1):
        if not isinstance(item, dict):
            raise CatalogConfigError(f"Категория #{index} должна быть объектом")

        category_id = _required_string(item, "id", f"Категория #{index}")
        category_name = _required_string(item, "name", f"Категория {category_id}")
        image = item.get("image")
        if image is not None and not isinstance(image, str):
            raise CatalogConfigError(f"Поле image категории {category_id} должно быть строкой")

        _validate_id(category_id, f"ID категории {category_id}")
        if category_id in category_ids:
            raise CatalogConfigError(f"Повторяющийся ID категории: {category_id}")
        category_ids.add(category_id)

        if len(make_category_callback(category_id).encode("utf-8")) > MAX_CALLBACK_DATA:
            raise CatalogConfigError(f"callback_data категории {category_id} длиннее 64 байт")

        models_raw = item.get("models")
        if not isinstance(models_raw, list) or not models_raw:
            raise CatalogConfigError(f"Категория {category_id} должна содержать хотя бы одну модель")

        model_ids: set[str] = set()
        models: list[Model] = []
        for model_index, model_item in enumerate(models_raw, start=1):
            if not isinstance(model_item, dict):
                raise CatalogConfigError(f"Модель #{model_index} в категории {category_id} должна быть объектом")

            model_id = _required_string(model_item, "id", f"Модель #{model_index} в категории {category_id}")
            model_name = _required_string(model_item, "name", f"Модель {model_id} в категории {category_id}")

            _validate_id(model_id, f"ID модели {model_id}")
            if model_id in model_ids:
                raise CatalogConfigError(f"Повторяющийся ID модели {model_id} в категории {category_id}")
            model_ids.add(model_id)

            if len(make_model_callback(category_id, model_id).encode("utf-8")) > MAX_CALLBACK_DATA:
                raise CatalogConfigError(
                    f"callback_data модели {category_id}/{model_id} длиннее 64 байт"
                )
            models.append(Model(id=model_id, name=model_name))

        categories.append(Category(id=category_id, name=category_name, image=image, models=tuple(models)))

    return Catalog(categories=tuple(categories))


def _required_string(item: dict[str, Any], field: str, context: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CatalogConfigError(f"{context}: поле {field} должно быть непустой строкой")
    return value.strip()


def _validate_id(value: str, context: str) -> None:
    if not _ID_RE.fullmatch(value):
        raise CatalogConfigError(f"{context} должен содержать только латиницу, цифры, '_' или '-'")
