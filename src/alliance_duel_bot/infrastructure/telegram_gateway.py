from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from alliance_duel_bot.domain.errors import (
    DeliveryError,
    RecipientUnavailableError,
)
from alliance_duel_bot.domain.ports import MessageGateway


logger = logging.getLogger(__name__)


class AiogramMessageGateway(MessageGateway):
    """Adapts Telegram's Bot API to the application's message gateway port."""

    def __init__(self, bot: Bot, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive.")
        self._bot = bot
        self._max_attempts = max_attempts

    async def send_text(self, chat_id: int, text: str) -> None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
                return
            except TelegramRetryAfter as error:
                if attempt == self._max_attempts:
                    raise DeliveryError(
                        f"Telegram rate limit persisted after {attempt} attempts."
                    ) from error
                logger.info(
                    "Telegram requested a retry in %s seconds.",
                    error.retry_after,
                )
                await asyncio.sleep(error.retry_after + 1)
            except TelegramForbiddenError as error:
                raise RecipientUnavailableError(
                    "The recipient no longer allows this bot to send messages."
                ) from error
            except TelegramAPIError as error:
                raise DeliveryError(
                    f"Telegram rejected the message: {error}"
                ) from error
