from __future__ import annotations

import asyncio
import logging
from datetime import date

from alliance_duel_bot.domain.errors import (
    DeliveryError,
    RecipientUnavailableError,
)
from alliance_duel_bot.domain.message_composer import MessageComposer
from alliance_duel_bot.domain.models import (
    ContentCatalog,
    DeliveryPart,
    DeliveryStatus,
    DeliverySummary,
    MessageType,
)
from alliance_duel_bot.domain.ports import (
    DeliveryLogRepository,
    MessageGateway,
    SubscriberRepository,
)


logger = logging.getLogger(__name__)


class DeliveryService:
    """Delivers manual selections and scheduled campaign messages."""

    def __init__(
        self,
        catalog: ContentCatalog,
        composer: MessageComposer,
        subscribers: SubscriberRepository,
        delivery_log: DeliveryLogRepository,
        gateway: MessageGateway,
        max_parallel_chats: int = 10,
        message_spacing_seconds: float = 1.1,
    ) -> None:
        if max_parallel_chats < 1:
            raise ValueError("max_parallel_chats must be positive.")
        if message_spacing_seconds < 0:
            raise ValueError("message_spacing_seconds cannot be negative.")

        self._catalog = catalog
        self._composer = composer
        self._subscribers = subscribers
        self._delivery_log = delivery_log
        self._gateway = gateway
        self._max_parallel_chats = max_parallel_chats
        self._message_spacing_seconds = message_spacing_seconds

    async def send_manual(
        self,
        chat_id: int,
        day_number: int,
        message_type: MessageType,
    ) -> DeliverySummary:
        parts = self._composer.compose_manual(
            self._catalog,
            day_number,
            message_type,
        )
        return await self._deliver_parts(chat_id, parts, send_date=None)

    async def send_scheduled(self, send_date: date) -> DeliverySummary:
        parts = self._composer.compose_scheduled(self._catalog, send_date)
        if not parts:
            logger.info("No campaign delivery is configured for %s.", send_date)
            return DeliverySummary()

        recipients = await self._subscribers.list_active()
        if not recipients:
            logger.info("There are no active subscribers for %s.", send_date)
            return DeliverySummary()

        semaphore = asyncio.Semaphore(self._max_parallel_chats)

        async def deliver_to_recipient(chat_id: int) -> DeliverySummary:
            async with semaphore:
                try:
                    return await self._deliver_parts(
                        chat_id,
                        parts,
                        send_date=send_date,
                    )
                except Exception:
                    logger.exception(
                        "Scheduled delivery failed for chat %s on %s.",
                        chat_id,
                        send_date,
                    )
                    return DeliverySummary(
                        total_parts=len(parts),
                        failed_parts=len(parts),
                    )

        reports = await asyncio.gather(
            *(deliver_to_recipient(item.chat_id) for item in recipients)
        )
        summary = DeliverySummary()
        for report in reports:
            summary = summary.combine(report)

        logger.info(
            "Delivery for %s: %s sent, %s failed, %s skipped.",
            send_date,
            summary.sent_parts,
            summary.failed_parts,
            summary.skipped_parts,
        )
        return summary

    async def _deliver_parts(
        self,
        chat_id: int,
        parts: tuple[DeliveryPart, ...],
        send_date: date | None,
    ) -> DeliverySummary:
        sent_parts = 0
        failed_parts = 0
        skipped_parts = 0

        for index, part in enumerate(parts):
            if index and self._message_spacing_seconds:
                await asyncio.sleep(self._message_spacing_seconds)

            if send_date is not None and await self._delivery_log.was_sent(
                send_date,
                chat_id,
                part.key,
            ):
                skipped_parts += 1
                continue

            try:
                await self._gateway.send_text(chat_id, part.text)
            except RecipientUnavailableError as error:
                await self._subscribers.unsubscribe(chat_id)
                await self._record_failure(send_date, chat_id, part.key, error)
                failed_parts += 1
                skipped_parts += len(parts) - index - 1
                logger.info(
                    "Chat %s was unsubscribed after Telegram rejected delivery.",
                    chat_id,
                )
                break
            except DeliveryError as error:
                await self._record_failure(send_date, chat_id, part.key, error)
                failed_parts += 1
                logger.warning(
                    "Could not send part %s to chat %s: %s",
                    part.key,
                    chat_id,
                    error,
                )
                continue

            if send_date is not None:
                await self._delivery_log.record(
                    send_date,
                    chat_id,
                    part.key,
                    DeliveryStatus.SENT,
                )
            sent_parts += 1

        return DeliverySummary(
            total_parts=len(parts),
            sent_parts=sent_parts,
            failed_parts=failed_parts,
            skipped_parts=skipped_parts,
        )

    async def _record_failure(
        self,
        send_date: date | None,
        chat_id: int,
        part_key: str,
        error: Exception,
    ) -> None:
        if send_date is not None:
            await self._delivery_log.record(
                send_date,
                chat_id,
                part_key,
                DeliveryStatus.FAILED,
                str(error),
            )
