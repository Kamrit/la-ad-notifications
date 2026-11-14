from __future__ import annotations

from datetime import date
from typing import Protocol

from alliance_duel_bot.domain.models import (
    ContentCatalog,
    DeliveryStatus,
    Subscriber,
)


class ContentRepository(Protocol):
    def load(self) -> ContentCatalog: ...


class SubscriberRepository(Protocol):
    async def subscribe(self, subscriber: Subscriber) -> None: ...

    async def unsubscribe(self, chat_id: int) -> None: ...

    async def list_active(self) -> list[Subscriber]: ...


class DeliveryLogRepository(Protocol):
    async def was_sent(self, send_date: date, chat_id: int, part_key: str) -> bool: ...

    async def record(
        self,
        send_date: date,
        chat_id: int,
        part_key: str,
        status: DeliveryStatus,
        error: str | None = None,
    ) -> None: ...


class MessageGateway(Protocol):
    async def send_text(self, chat_id: int, text: str) -> None: ...
