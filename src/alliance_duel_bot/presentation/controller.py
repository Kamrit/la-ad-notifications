from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from alliance_duel_bot.application.delivery_service import DeliveryService
from alliance_duel_bot.application.subscription_service import SubscriptionService
from alliance_duel_bot.domain.errors import ContentValidationError
from alliance_duel_bot.domain.models import MessageType, Subscriber
from alliance_duel_bot.presentation.keyboards import TelegramKeyboardFactory


logger = logging.getLogger(__name__)


class PrivateChatController:
    """Maps Telegram updates to application use cases."""

    def __init__(
        self,
        subscriptions: SubscriptionService,
        deliveries: DeliveryService,
        keyboards: TelegramKeyboardFactory,
    ) -> None:
        self._subscriptions = subscriptions
        self._deliveries = deliveries
        self._keyboards = keyboards
        self.router = Router(name="private-chat")
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.stop, Command("stop"))
        self.router.message.register(self.choose, Command("choose"))
        self.router.message.register(self.help, Command("help"))
        self.router.callback_query.register(
            self.show_days,
            F.data == "menu:choose",
        )
        self.router.callback_query.register(
            self.show_home,
            F.data == "menu:home",
        )
        self.router.callback_query.register(
            self.pause_from_button,
            F.data == "subscription:stop",
        )
        self.router.callback_query.register(
            self.show_message_types,
            F.data.startswith("day:"),
        )
        self.router.callback_query.register(
            self.send_selected_message,
            F.data.startswith("type:"),
        )

    async def start(self, message: Message) -> None:
        if not self._is_private(message):
            await message.answer("Please open a private chat with me to subscribe.")
            return

        user = message.from_user
        if user is None:
            return

        full_name = " ".join(
            part for part in (user.first_name, user.last_name) if part
        )
        await self._subscriptions.subscribe(
            Subscriber(
                chat_id=message.chat.id,
                full_name=full_name or "Telegram user",
                username=user.username,
            )
        )
        await message.answer(
            "You are subscribed to daily Alliance Duel messages.\n"
            "Choose a campaign day and message type below. "
            "Send /stop to pause automatic messages.",
            reply_markup=self._keyboards.main_menu(),
        )

    async def stop(self, message: Message) -> None:
        if not self._is_private(message):
            await message.answer("Please use this command in a private chat.")
            return

        await self._subscriptions.unsubscribe(message.chat.id)
        await message.answer(
            "Automatic messages are paused. Send /start to subscribe again.",
            reply_markup=self._keyboards.main_menu(),
        )

    async def choose(self, message: Message) -> None:
        if not self._is_private(message):
            await message.answer("Please use this command in a private chat.")
            return
        await message.answer(
            "Choose a campaign day:",
            reply_markup=self._keyboards.campaign_days(),
        )

    async def help(self, message: Message) -> None:
        if not self._is_private(message):
            await message.answer("Please use this command in a private chat.")
            return
        await message.answer(
            "Alliance Duel Bot\n\n"
            "/start - subscribe to automatic private messages\n"
            "/choose - select a campaign day and message type\n"
            "/stop - pause automatic messages\n"
            "/help - show this help"
        )

    async def show_days(self, callback: CallbackQuery) -> None:
        message = await self._private_callback_message(callback)
        if message is None:
            return
        await callback.answer()
        await message.edit_text(
            "Choose a campaign day:",
            reply_markup=self._keyboards.campaign_days(),
        )

    async def show_home(self, callback: CallbackQuery) -> None:
        message = await self._private_callback_message(callback)
        if message is None:
            return
        await callback.answer()
        await message.edit_text(
            "Alliance Duel Bot",
            reply_markup=self._keyboards.main_menu(),
        )

    async def pause_from_button(self, callback: CallbackQuery) -> None:
        message = await self._private_callback_message(callback)
        if message is None:
            return
        await self._subscriptions.unsubscribe(message.chat.id)
        await callback.answer("Notifications paused.")
        await message.edit_text(
            "Automatic messages are paused. Send /start to subscribe again.",
            reply_markup=self._keyboards.main_menu(),
        )

    async def show_message_types(self, callback: CallbackQuery) -> None:
        message = await self._private_callback_message(callback)
        if message is None or callback.data is None:
            return

        try:
            day_number = int(callback.data.split(":", maxsplit=1)[1])
            if day_number not in range(1, 6):
                raise ValueError
        except ValueError:
            await callback.answer("That campaign day is not available.", show_alert=True)
            return

        await callback.answer()
        await message.edit_text(
            f"Choose a message type for Day {day_number}:",
            reply_markup=self._keyboards.message_types(day_number),
        )

    async def send_selected_message(self, callback: CallbackQuery) -> None:
        message = await self._private_callback_message(callback)
        if message is None or callback.data is None:
            return

        try:
            _, day_value, message_type_value = callback.data.split(":", maxsplit=2)
            day_number = int(day_value)
            if day_number not in range(1, 6):
                raise ValueError
            message_type = MessageType(message_type_value)
        except ValueError:
            await callback.answer("That selection is not available.", show_alert=True)
            return

        await callback.answer("Sending your messages.")
        await message.edit_text(
            f"Sending the Day {day_number} "
            f"{message_type.value.replace('_', ' ')}..."
        )

        try:
            summary = await self._deliveries.send_manual(
                message.chat.id,
                day_number,
                message_type,
            )
        except ContentValidationError:
            logger.exception("Campaign content failed validation during manual send.")
            await message.answer(
                "The selected campaign content is unavailable. Please contact the bot owner.",
                reply_markup=self._keyboards.main_menu(),
            )
            return
        except Exception:
            logger.exception("Manual delivery failed for chat %s.", message.chat.id)
            await message.answer(
                "I could not send the selected messages. Please try again later.",
                reply_markup=self._keyboards.main_menu(),
            )
            return

        if summary.is_successful:
            result = f"Sent {summary.sent_parts} message(s)."
        else:
            result = (
                f"Sent {summary.sent_parts} of {summary.total_parts} message(s). "
                f"{summary.failed_parts} part(s) could not be delivered."
            )
        await message.answer(
            result,
            reply_markup=self._keyboards.main_menu(),
        )

    async def _private_callback_message(
        self, callback: CallbackQuery
    ) -> Message | None:
        message = callback.message
        if not isinstance(message, Message) or not self._is_private(message):
            await callback.answer(
                "Use the bot in a private chat.",
                show_alert=True,
            )
            return None
        return message

    @staticmethod
    def _is_private(message: Message) -> bool:
        return message.chat.type == "private"
