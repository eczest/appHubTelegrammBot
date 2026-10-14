from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

logger = logging.getLogger(__name__)

_BOT_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class SettingsError(ValueError):
    """Raised when environment variables are missing or invalid."""


class ContentConfigError(ValueError):
    """Raised when content.yaml contains invalid data."""


@dataclass(frozen=True)
class Settings:
    bot_token: str
    manager_chat_id: int
    manager_topic_id: int | None
    channel_id: int
    admin_user_ids: frozenset[int]
    channel_url: str
    timezone: str
    log_level: str


@dataclass(frozen=True)
class StoreContent:
    name: str
    city: str
    addresses: tuple[str, ...]
    phone: str
    working_hours: str
    channel_url: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    manager_chat_id_raw = os.getenv("MANAGER_CHAT_ID", "").strip()
    manager_topic_id_raw = os.getenv("MANAGER_TOPIC_ID", "").strip()
    channel_id_raw = os.getenv("CHANNEL_ID", "").strip()
    admin_user_ids_raw = os.getenv("ADMIN_USER_IDS", "").strip()
    channel_url_raw = os.getenv("CHANNEL_URL", "").strip()
    timezone = os.getenv("TIMEZONE", "Asia/Yekaterinburg").strip() or "Asia/Yekaterinburg"
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

    if not _BOT_TOKEN_RE.fullmatch(bot_token):
        raise SettingsError("BOT_TOKEN отсутствует или имеет неверный формат")

    try:
        manager_chat_id = int(manager_chat_id_raw)
    except ValueError as exc:
        raise SettingsError("MANAGER_CHAT_ID отсутствует или не является числом") from exc

    manager_topic_id = parse_optional_topic_id(manager_topic_id_raw)
    try:
        channel_id = int(channel_id_raw)
    except ValueError as exc:
        raise SettingsError("CHANNEL_ID отсутствует или не является числом") from exc

    admin_user_ids = parse_admin_user_ids(admin_user_ids_raw)
    channel_url = channel_url_raw or build_channel_base_link(channel_id)

    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise SettingsError(f"TIMEZONE не найден: {timezone}") from exc

    if log_level not in _LOG_LEVELS:
        raise SettingsError(f"LOG_LEVEL должен быть одним из: {', '.join(sorted(_LOG_LEVELS))}")

    return Settings(
        bot_token=bot_token,
        manager_chat_id=manager_chat_id,
        manager_topic_id=manager_topic_id,
        channel_id=channel_id,
        admin_user_ids=admin_user_ids,
        channel_url=channel_url,
        timezone=timezone,
        log_level=log_level,
    )


def parse_optional_topic_id(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        topic_id = int(value)
    except ValueError as exc:
        raise SettingsError("MANAGER_TOPIC_ID должен быть числом или пустым") from exc
    if topic_id <= 0:
        raise SettingsError("MANAGER_TOPIC_ID должен быть положительным числом")
    return topic_id


def parse_admin_user_ids(value: str | None) -> frozenset[int]:
    if value is None or not value.strip():
        raise SettingsError("ADMIN_USER_IDS должен содержать хотя бы один Telegram ID администратора")

    ids: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            user_id = int(item)
        except ValueError as exc:
            raise SettingsError(f"ADMIN_USER_IDS содержит нечисловое значение: {item}") from exc
        if user_id <= 0:
            raise SettingsError("ADMIN_USER_IDS должен содержать положительные Telegram ID")
        ids.add(user_id)

    if not ids:
        raise SettingsError("ADMIN_USER_IDS должен содержать хотя бы один Telegram ID администратора")
    return frozenset(ids)


def is_admin_user(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id in settings.admin_user_ids


def build_channel_base_link(channel_id: int) -> str:
    channel_id_text = str(channel_id)
    if channel_id_text.startswith("-100"):
        return f"https://t.me/c/{channel_id_text[4:]}"
    return f"https://t.me/c/{abs(channel_id)}"


def build_channel_message_link(channel_id: int, message_id: int) -> str:
    return f"{build_channel_message_base_link(channel_id)}/{message_id}"


def build_channel_message_base_link(channel: int | str) -> str:
    if isinstance(channel, str):
        username = channel.strip()
        if username.startswith("@"):
            username = username[1:]
        return f"https://t.me/{username}"
    return build_channel_base_link(channel)


def load_content(path: str | Path) -> StoreContent:
    content_path = Path(path)
    try:
        raw = yaml.safe_load(content_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContentConfigError(f"Не удалось прочитать {content_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ContentConfigError(f"Файл {content_path} содержит ошибку YAML: {exc}") from exc

    store_raw = raw.get("store") if isinstance(raw, dict) else None
    if not isinstance(store_raw, dict):
        raise ContentConfigError("content.yaml должен содержать объект store")

    addresses_raw = store_raw.get("addresses")
    if not isinstance(addresses_raw, list) or not addresses_raw:
        raise ContentConfigError("store.addresses должен быть непустым списком строк")

    addresses = tuple(_required_string(address, "store.addresses") for address in addresses_raw)
    content = StoreContent(
        name=_required_string(store_raw.get("name"), "store.name"),
        city=_required_string(store_raw.get("city"), "store.city"),
        addresses=addresses,
        phone=_required_string(store_raw.get("phone"), "store.phone"),
        working_hours=_required_string(store_raw.get("working_hours"), "store.working_hours"),
        channel_url=_required_string(store_raw.get("channel_url"), "store.channel_url"),
    )
    logger.info("Content loaded from %s", content_path)
    return content


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentConfigError(f"{name} должен быть непустой строкой")
    return value.strip()
