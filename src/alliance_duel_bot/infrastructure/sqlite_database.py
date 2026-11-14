from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


class SQLiteDatabase:
    """Owns SQLite schema setup and short-lived async connections."""

    CURRENT_SCHEMA_VERSION = 1

    def __init__(self, path: Path, timeout_seconds: float = 30.0) -> None:
        self.path = path
        self._timeout_seconds = timeout_seconds

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connection() as connection:
            cursor = await connection.execute("PRAGMA journal_mode=WAL")
            await cursor.close()
            cursor = await connection.execute("PRAGMA user_version")
            row = await cursor.fetchone()
            await cursor.close()
            current_version = int(row[0]) if row else 0

            if current_version > self.CURRENT_SCHEMA_VERSION:
                raise RuntimeError(
                    "The database schema is newer than this application supports."
                )

            await connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    is_subscribed INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS ix_subscribers_is_subscribed
                    ON subscribers (is_subscribed);

                CREATE TABLE IF NOT EXISTS delivery_log (
                    send_date TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    part_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (send_date, chat_id, part_key)
                );

                CREATE INDEX IF NOT EXISTS ix_delivery_log_status
                    ON delivery_log (status);
                """
            )
            await connection.execute(
                f"PRAGMA user_version = {self.CURRENT_SCHEMA_VERSION}"
            )

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await aiosqlite.connect(
            self.path,
            timeout=self._timeout_seconds,
        )
        connection.row_factory = aiosqlite.Row
        try:
            yield connection
            if connection.in_transaction:
                await connection.commit()
        except Exception:
            if connection.in_transaction:
                await connection.rollback()
            raise
        finally:
            await connection.close()
