from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def localized_now(timezone: str) -> datetime:
    return datetime.now(ZoneInfo(timezone))
