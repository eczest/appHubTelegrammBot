from pathlib import Path

from app.admin_access import AdminRegistry, is_authorized_admin, is_owner
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        manager_chat_id=-1001,
        manager_topic_id=None,
        channel_id=-1002,
        admin_user_ids=frozenset({10}),
        channel_url="https://t.me/example",
        timezone="Asia/Yekaterinburg",
        log_level="INFO",
    )


def test_dynamic_admin_registry(tmp_path: Path) -> None:
    registry = AdminRegistry(tmp_path / "admins.json")
    settings = _settings()

    assert is_owner(10, settings)
    assert is_authorized_admin(20, settings, registry) is False
    assert registry.add(20) is True
    assert registry.add(20) is False
    assert is_authorized_admin(20, settings, registry) is True
    assert registry.remove(20) is True
    assert is_authorized_admin(20, settings, registry) is False

