from __future__ import annotations

import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from alliance_duel_bot.application.daily_scheduler import DailyScheduler
from alliance_duel_bot.domain.models import ContentCatalog, SchedulePolicy


KYIV = ZoneInfo("Europe/Kyiv")


class DailySchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        policy = SchedulePolicy(
            timezone=KYIV,
            send_time=time(21, 0),
            weekday_to_campaign_day={},
            language_batches=(),
            message_order=(),
            friday_action="send_friday_to_saturday_shield_reminder",
            saturday_action="no_alliance_duel_message",
            catchup_grace_minutes=10,
        )
        catalog = ContentCatalog(
            event_name="Test event",
            campaign_days={},
            schedule=policy,
            friday_shield_reminder={},
        )
        self.scheduler = DailyScheduler(catalog, delivery_service=None)

    def test_next_run_is_today_before_scheduled_time(self) -> None:
        now = datetime(2026, 11, 15, 20, 59, tzinfo=KYIV)

        self.assertEqual(
            self.scheduler.next_run_at(now, None),
            datetime(2026, 11, 15, 21, 0, tzinfo=KYIV),
        )

    def test_missed_run_is_caught_up_within_grace_period(self) -> None:
        now = datetime(2026, 11, 15, 21, 5, tzinfo=KYIV)

        self.assertEqual(
            self.scheduler.next_run_at(now, None),
            datetime(2026, 11, 15, 21, 0, tzinfo=KYIV),
        )

    def test_missed_run_is_skipped_after_grace_period(self) -> None:
        now = datetime(2026, 11, 15, 21, 11, tzinfo=KYIV)

        self.assertEqual(
            self.scheduler.next_run_at(now, None),
            datetime(2026, 11, 16, 21, 0, tzinfo=KYIV),
        )

    def test_already_attempted_day_is_not_sent_again(self) -> None:
        now = datetime(2026, 11, 15, 21, 1, tzinfo=KYIV)

        self.assertEqual(
            self.scheduler.next_run_at(now, date(2026, 11, 15)),
            datetime(2026, 11, 16, 21, 0, tzinfo=KYIV),
        )

    def test_schedule_handles_utc_input(self) -> None:
        now = datetime(2026, 11, 15, 18, 0, tzinfo=ZoneInfo("UTC"))

        scheduled = self.scheduler.next_run_at(now, None)

        self.assertEqual(scheduled, datetime(2026, 11, 15, 21, 0, tzinfo=KYIV))


if __name__ == "__main__":
    unittest.main()
