from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import parse_optional_topic_id
from app.utils.formatting import format_product_request_html, html_escape


@dataclass
class UserStub:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None


def test_html_escape() -> None:
    assert html_escape("<b>A&B</b>") == "&lt;b&gt;A&amp;B&lt;/b&gt;"


def test_format_product_request_with_username() -> None:
    user = UserStub(id=123456789, first_name="Савелий", last_name="Лакиза", username="username")
    text = format_product_request_html(
        category_name="iPhone",
        model_name="iPhone 17 Pro Max",
        user=user,
        request_time=datetime(2026, 9, 8, 18, 42, tzinfo=ZoneInfo("Asia/Yekaterinburg")),
    )
    assert "<b>Категория:</b> iPhone <b>Модель:</b> iPhone 17 Pro Max" in text
    assert "<b>Клиент:</b> Савелий Лакиза" in text
    assert "<b>Username:</b> @username" in text
    assert "<code>123456789</code>" in text
    assert 'tg://user?id=123456789' in text
    assert "08.09.2026 18:42" in text


def test_format_product_request_without_username_and_last_name() -> None:
    user = UserStub(id=7, first_name="Alex <Admin>", last_name=None, username=None)
    text = format_product_request_html(
        category_name="Dyson & Sony",
        model_name="Model <X>",
        user=user,
        request_time=datetime(2026, 9, 8, 18, 42),
    )
    assert "None" not in text
    assert "<b>Username:</b> не указан" in text
    assert "Alex &lt;Admin&gt;" in text
    assert "Dyson &amp; Sony" in text
    assert "Model &lt;X&gt;" in text


def test_optional_manager_topic_id() -> None:
    assert parse_optional_topic_id("") is None
    assert parse_optional_topic_id(None) is None
    assert parse_optional_topic_id("42") == 42
