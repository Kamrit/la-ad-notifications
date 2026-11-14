from __future__ import annotations

import asyncio

from aiogram import Bot

from alliance_duel_bot.config import Settings


async def main() -> None:
    settings = Settings.from_environment()
    bot = Bot(token=settings.bot_token)
    try:
        bot_identity = await bot.get_me()
        print(
            "Telegram API connection successful: "
            f"@{bot_identity.username} (ID {bot_identity.id})"
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
