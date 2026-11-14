# Alliance Duel Telegram Bot

An object-oriented Python application that sends Alliance Duel campaign content to Telegram private chats and lets each subscriber request messages for any campaign day.

## Architecture

The project separates business rules from Telegram and persistence:

- Domain models represent campaign days, message types, schedule policy, subscribers, and delivery parts.
- Application services handle subscriptions, message delivery, retries, and scheduled sends.
- Infrastructure adapters read the JSON catalog, persist subscribers and delivery records in SQLite, and send messages through Telegram.
- The presentation controller maps Telegram commands and inline-button callbacks to application services.
- The bootstrap module wires these components and starts polling and the scheduler.

## Features

- Sends a daily campaign packet at 21:00 in Europe/Kyiv.
- Sends the alliance letter first, then three note messages with two languages each.
- Sends a separate Friday-to-Saturday shield reminder on Friday at 21:00.
- Skips Saturday because the campaign has no Saturday content.
- Provides a day-first, message-type-second inline menu.
- Subscribes users through /start and pauses automatic messages through /stop.
- Records each scheduled message part in SQLite to support safe retry within the configured grace window.
- Reads campaign messages and schedule settings from data/alliance_duel_messages.json.
- Loads local secrets from .env without logging the token.

## Delivery schedule

| Local send time | Content |
| --- | --- |
| Sunday, 21:00 | Day 1 for Monday |
| Monday, 21:00 | Day 2 for Tuesday |
| Tuesday, 21:00 | Day 3 for Wednesday |
| Wednesday, 21:00 | Day 4 for Thursday |
| Thursday, 21:00 | Day 5 for Friday |
| Friday, 21:00 | Friday-to-Saturday shield reminder |
| Saturday, 21:00 | No message |

The bot sends campaign text only in Telegram private chats. Users copy the chosen text into the game themselves.

## Project layout

~~~~text
telegram_ad_bot/
├── src/
│   └── alliance_duel_bot/
│       ├── application/
│       ├── domain/
│       ├── infrastructure/
│       ├── presentation/
│       ├── bootstrap.py
│       ├── config.py
│       └── __main__.py
├── data/
│   └── alliance_duel_messages.json
├── tests/
├── runtime/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
~~~~

## Create and configure the Telegram bot

1. Create a bot with @BotFather and copy its token.
2. Copy .env.example to .env in the project root.
3. Replace the placeholder BOT_TOKEN value.

The application loads .env for local runs. Docker Compose passes the same file into the container. Keep .env private; it is excluded by .gitignore and .dockerignore. Never paste the bot token into chat or commit it to source control.

## Run locally on Windows

From the project root:

~~~~powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
~~~~

Add the token to .env, then start the bot:

~~~~powershell
python -m alliance_duel_bot
~~~~

## Run with Docker

Copy .env.example to .env, add the token, then run:

~~~~powershell
docker compose up --build -d
docker compose logs -f bot
~~~~

The SQLite database is persisted in runtime/.

## User commands

- /start subscribes the user and opens the menu.
- /choose opens the day and message-type selector.
- /stop pauses automatic messages.
- /help lists the commands.

Alliance message sends the English and Russian versions together. Alliance note sends all three language pairs: English/Russian, German/Ukrainian, and Portuguese/Korean.

Each recipient must start the bot once before it can send private messages to them.

## Configuration and content

Environment variables:

| Name | Default | Purpose |
| --- | --- | --- |
| BOT_TOKEN | Required | Telegram BotFather token |
| DATABASE_PATH | runtime/bot.sqlite3 | SQLite database path |
| CONTENT_PATH | data/alliance_duel_messages.json | Campaign catalog path |
| LOG_LEVEL | INFO | Application log level |

The JSON catalog is validated at startup. Restart the application after editing it.

## Tests

The unit suite uses Python's standard unittest framework and does not require a Telegram token:

~~~~powershell
python -m unittest discover -s tests -v
~~~~

To verify that the token is valid without starting polling, run:

~~~~powershell
python scripts/telegram_smoke_check.py
~~~~

The smoke check prints the bot username and Telegram ID; it never prints the token. Keep the bot process running on an always-on computer or server. Failed scheduled message parts are retried every minute within the configured grace period; the default is ten minutes. A sent part is recorded in SQLite so a retry does not send that part twice.
