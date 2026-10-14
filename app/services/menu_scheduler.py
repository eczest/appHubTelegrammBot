from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot

from app.config import Settings
from app.menu_store import MenuStore
from app.services.channel_menu_publisher import ChannelMenuPublishError, publish_fallback_channel_menu
from app.timer_state import load_timer_state, next_timer_run, save_timer_state

logger = logging.getLogger(__name__)


class MenuScheduler:
    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        menu_store: MenuStore,
        timer_path: str | Path,
        channel_state_path: str | Path,
        poll_seconds: int = 15,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.menu_store = menu_store
        self.timer_path = Path(timer_path)
        self.channel_state_path = Path(channel_state_path)
        self.poll_seconds = poll_seconds

    async def run(self) -> None:
        logger.info("Menu scheduler started")
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected menu scheduler error")
            await asyncio.sleep(self.poll_seconds)

    async def _tick(self) -> None:
        state = load_timer_state(self.timer_path)
        if not state.enabled or not state.next_run_at:
            return
        now = datetime.now(ZoneInfo(self.settings.timezone))
        next_run = datetime.fromisoformat(state.next_run_at)
        if now < next_run:
            return

        try:
            menu = self.menu_store.load(require_filled_urls=True)
            published, link = await publish_fallback_channel_menu(
                self.bot,
                self.settings,
                menu,
                self.channel_state_path,
                now,
            )
            logger.info("Scheduled menu published: message_id=%s link=%s", published.message_id, link)
        except ChannelMenuPublishError:
            logger.exception("Scheduled menu publication failed")
        finally:
            save_timer_state(self.timer_path, next_timer_run(state, now))

