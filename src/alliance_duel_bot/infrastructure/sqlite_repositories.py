from __future__ import annotations

from datetime import date, datetime, timezone

from alliance_duel_bot.domain.models import DeliveryStatus, Subscriber
from alliance_duel_bot.domain.ports import (
    DeliveryLogRepository,
    SubscriberRepository,
)
from alliance_duel_bot.infrastructure.sqlite_database import SQLiteDatabase


class SQLiteSubscriberRepository(SubscriberRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def subscribe(self, subscriber: Subscriber) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO subscribers
                    (chat_id, username, full_name, is_subscribed, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    is_subscribed = 1,
                    updated_at = excluded.updated_at
                """,
                (
                    subscriber.chat_id,
                    subscriber.username,
                    subscriber.full_name,
                    now,
                    now,
                ),
            )

    async def unsubscribe(self, chat_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self._database.connection() as connection:
            await connection.execute(
                """
                UPDATE subscribers
                SET is_subscribed = 0, updated_at = ?
                WHERE chat_id = ?
                """,
                (now, chat_id),
            )

    async def list_active(self) -> list[Subscriber]:
        async with self._database.connection() as connection:
            async with connection.execute(
                """
                SELECT chat_id, username, full_name
                FROM subscribers
                WHERE is_subscribed = 1
                ORDER BY chat_id
                """
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            Subscriber(
                chat_id=int(row["chat_id"]),
                username=row["username"],
                full_name=str(row["full_name"]),
            )
            for row in rows
        ]


class SQLiteDeliveryLogRepository(DeliveryLogRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def was_sent(
        self,
        send_date: date,
        chat_id: int,
        part_key: str,
    ) -> bool:
        async with self._database.connection() as connection:
            async with connection.execute(
                """
                SELECT 1
                FROM delivery_log
                WHERE send_date = ? AND chat_id = ? AND part_key = ?
                    AND status = ?
                """,
                (
                    send_date.isoformat(),
                    chat_id,
                    part_key,
                    DeliveryStatus.SENT.value,
                ),
            ) as cursor:
                return await cursor.fetchone() is not None

    async def record(
        self,
        send_date: date,
        chat_id: int,
        part_key: str,
        status: DeliveryStatus,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO delivery_log
                    (send_date, chat_id, part_key, status, error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(send_date, chat_id, part_key) DO UPDATE SET
                    status = excluded.status,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    send_date.isoformat(),
                    chat_id,
                    part_key,
                    status.value,
                    error,
                    now,
                ),
            )
