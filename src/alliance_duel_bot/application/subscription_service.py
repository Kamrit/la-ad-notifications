from alliance_duel_bot.domain.models import Subscriber
from alliance_duel_bot.domain.ports import SubscriberRepository


class SubscriptionService:
    """Coordinates private-chat subscription changes."""

    def __init__(self, subscribers: SubscriberRepository) -> None:
        self._subscribers = subscribers

    async def subscribe(self, subscriber: Subscriber) -> None:
        await self._subscribers.subscribe(subscriber)

    async def unsubscribe(self, chat_id: int) -> None:
        await self._subscribers.unsubscribe(chat_id)
