from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from alliance_duel_bot.domain.models import MessageType


class TelegramKeyboardFactory:
    """Builds the inline keyboards shown in private chats."""

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Choose a message",
                        callback_data="menu:choose",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Pause notifications",
                        callback_data="subscription:stop",
                    )
                ],
            ]
        )

    @staticmethod
    def campaign_days() -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton(
                    text=f"Day {day}",
                    callback_data=f"day:{day}",
                )
                for day in range(start, min(start + 3, 6))
            ]
            for start in (1, 4)
        ]
        rows.append(
            [InlineKeyboardButton(text="Back", callback_data="menu:home")]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @staticmethod
    def message_types(day_number: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Alliance message",
                        callback_data=(
                            f"type:{day_number}:{MessageType.ALLIANCE_MESSAGE.value}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Alliance note",
                        callback_data=(
                            f"type:{day_number}:{MessageType.ALLIANCE_NOTE.value}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Back",
                        callback_data="menu:choose",
                    )
                ],
            ]
        )
