from __future__ import annotations

import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

from app.channel_menu import ChannelMenuConfigError
from app.config import ContentConfigError, SettingsError, load_content, load_settings
from app.handlers import admin, contacts, questions, start
from app.services.menu_scheduler import MenuScheduler
from app.services.manager_notifications import RecentActionGuard

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


async def handle_unexpected_error(event: ErrorEvent) -> bool:
    logger.exception("Unhandled update error", exc_info=event.exception)
    update = event.update
    message = getattr(update, "message", None) or getattr(update, "callback_query", None)
    if getattr(message, "message", None):
        message = message.message
    if message:
        chat = getattr(message, "chat", None)
        if chat is not None and chat.type != "private":
            return True
        try:
            await message.answer("Произошла ошибка. Пожалуйста, попробуйте ещё раз немного позже.")
        except Exception:
            logger.exception("Failed to notify user about unhandled error")
    return True


async def main() -> None:
    load_dotenv()
    settings = load_settings()
    configure_logging(settings.log_level)

    try:
        content = load_content("config/content.yaml")
    except (ChannelMenuConfigError, ContentConfigError):
        logger.exception("Configuration error")
        raise

    logger.info("Starting bot")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    try:
        dp = Dispatcher(
            content=content,
            settings=settings,
            recent_guard=RecentActionGuard(),
        )
        dp.include_router(admin.router)
        dp.include_router(start.router)
        dp.include_router(contacts.router)
        dp.include_router(questions.router)
        dp.errors.register(handle_unexpected_error)

        logger.info("Deleting webhook before long polling")
        await bot.delete_webhook(drop_pending_updates=True)

        scheduler = MenuScheduler(
            bot=bot,
            settings=settings,
            menu_store=admin.menu_store,
            timer_path=admin.TIMER_STATE_PATH,
            channel_state_path=admin.CHANNEL_MENU_STATE_PATH,
        )

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)

        polling_task = asyncio.create_task(dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()))
        scheduler_task = asyncio.create_task(scheduler.run())
        stop_task = asyncio.create_task(stop_event.wait())
        try:
            done, _pending = await asyncio.wait({polling_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
            if stop_task in done:
                logger.info("Stop signal received")
                polling_task.cancel()
                await asyncio.gather(polling_task, return_exceptions=True)
            else:
                await polling_task
        finally:
            stop_task.cancel()
            scheduler_task.cancel()
            await asyncio.gather(scheduler_task, return_exceptions=True)
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (SettingsError, ChannelMenuConfigError, ContentConfigError) as exc:
        logging.basicConfig(level=logging.ERROR, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
        logging.getLogger(__name__).error("Startup failed: %s", exc)
        raise SystemExit(1) from exc
