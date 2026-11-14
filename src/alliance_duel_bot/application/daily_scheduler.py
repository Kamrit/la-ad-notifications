from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from alliance_duel_bot.application.delivery_service import DeliveryService
from alliance_duel_bot.domain.models import ContentCatalog


logger = logging.getLogger(__name__)


class DailyScheduler:
    """Runs one scheduled campaign delivery at the configured local wall-clock time."""

    def __init__(
        self,
        catalog: ContentCatalog,
        delivery_service: DeliveryService,
        retry_interval_seconds: float = 60,
    ) -> None:
        if retry_interval_seconds <= 0:
            raise ValueError("retry_interval_seconds must be positive.")
        self._catalog = catalog
        self._delivery_service = delivery_service
        self._retry_interval_seconds = retry_interval_seconds

    def next_run_at(
        self,
        now: datetime,
        last_attempted_date: date | None,
    ) -> datetime:
        timezone = self._catalog.schedule.timezone
        local_now = now.astimezone(timezone)
        today_run = datetime.combine(
            local_now.date(),
            self._catalog.schedule.send_time,
            tzinfo=timezone,
        )

        if local_now < today_run:
            return today_run

        grace_deadline = today_run + timedelta(
            minutes=self._catalog.schedule.catchup_grace_minutes
        )
        if (
            last_attempted_date != local_now.date()
            and local_now <= grace_deadline
        ):
            return today_run

        next_date = local_now.date() + timedelta(days=1)
        return datetime.combine(
            next_date,
            self._catalog.schedule.send_time,
            tzinfo=timezone,
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        last_attempted_date: date | None = None
        timezone = self._catalog.schedule.timezone
        grace_period = timedelta(
            minutes=self._catalog.schedule.catchup_grace_minutes
        )

        while not stop_event.is_set():
            now = datetime.now(timezone)
            scheduled_at = self.next_run_at(now, last_attempted_date)
            delay = max((scheduled_at - now).total_seconds(), 0)
            logger.info(
                "Next scheduled delivery is %s.",
                scheduled_at.isoformat(timespec="minutes"),
            )

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
                break
            except TimeoutError:
                pass

            current_time = datetime.now(timezone)
            send_date = scheduled_at.date()
            if (
                current_time.date() != send_date
                or current_time > scheduled_at + grace_period
            ):
                logger.warning(
                    "Skipping the missed delivery for %s; it is outside "
                    "the configured grace period.",
                    send_date,
                )
                last_attempted_date = send_date
                continue

            deadline = scheduled_at + grace_period
            while not stop_event.is_set():
                try:
                    summary = await self._delivery_service.send_scheduled(send_date)
                except Exception:
                    logger.exception("Scheduled delivery failed for %s.", send_date)
                    failed_parts = 1
                else:
                    failed_parts = summary.failed_parts

                now = datetime.now(timezone)
                remaining_seconds = (deadline - now).total_seconds()
                if failed_parts == 0 or remaining_seconds <= 0:
                    break

                retry_delay = min(
                    self._retry_interval_seconds,
                    remaining_seconds,
                )
                logger.warning(
                    "%s message part(s) failed for %s; retrying in %.0f seconds.",
                    failed_parts,
                    send_date,
                    retry_delay,
                )
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=retry_delay,
                    )
                except TimeoutError:
                    continue
                break

            last_attempted_date = send_date
