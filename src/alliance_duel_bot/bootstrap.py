from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from alliance_duel_bot.application.daily_scheduler import DailyScheduler
from alliance_duel_bot.application.delivery_service import DeliveryService
from alliance_duel_bot.application.subscription_service import SubscriptionService
from alliance_duel_bot.config import Settings
from alliance_duel_bot.domain.message_composer import MessageComposer
from alliance_duel_bot.infrastructure.json_content_repository import (
    JsonContentRepository,
)
from alliance_duel_bot.infrastructure.sqlite_database import SQLiteDatabase
from alliance_duel_bot.infrastructure.sqlite_repositories import (
    SQLiteDeliveryLogRepository,
    SQLiteSubscriberRepository,
)
from alliance_duel_bot.infrastructure.telegram_gateway import AiogramMessageGateway
from alliance_duel_bot.presentation.controller import PrivateChatController
from alliance_duel_bot.presentation.keyboards import TelegramKeyboardFactory


class BotApplication:
    """Composition root that wires infrastructure and application services."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self) -> None:
        self._configure_logging()
        logger = logging.getLogger(__name__)
        catalog = JsonContentRepository(self._settings.content_path).load()

        database = SQLiteDatabase(self._settings.database_path)
        await database.initialize()

        bot = Bot(token=self._settings.bot_token)
        subscribers = SQLiteSubscriberRepository(database)
        delivery_log = SQLiteDeliveryLogRepository(database)
        gateway = AiogramMessageGateway(bot)
        composer = MessageComposer()

        subscription_service = SubscriptionService(subscribers)
        delivery_service = DeliveryService(
            catalog=catalog,
            composer=composer,
            subscribers=subscribers,
            delivery_log=delivery_log,
            gateway=gateway,
        )
        controller = PrivateChatController(
            subscriptions=subscription_service,
            deliveries=delivery_service,
            keyboards=TelegramKeyboardFactory(),
        )

        dispatcher = Dispatcher()
        dispatcher.include_router(controller.router)
        stop_event = asyncio.Event()
        scheduler = DailyScheduler(catalog, delivery_service)
        scheduler_task = asyncio.create_task(
            scheduler.run(stop_event),
            name="daily-delivery-scheduler",
        )
        logger.info("Alliance Duel Bot is starting.")

        try:
            await dispatcher.start_polling(
                bot,
                close_bot_session=False,
            )
        finally:
            stop_event.set()
            await scheduler_task
            await bot.session.close()

    def _configure_logging(self) -> None:
        level = getattr(logging, self._settings.log_level, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def run_application() -> None:
    from alliance_duel_bot.config import Settings

    settings = Settings.from_environment()
    asyncio.run(BotApplication(settings).run())
