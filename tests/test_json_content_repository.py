from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from alliance_duel_bot.domain.message_composer import MessageComposer
from alliance_duel_bot.domain.models import MessageType
from alliance_duel_bot.infrastructure.json_content_repository import (
    JsonContentRepository,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG = JsonContentRepository(
    PROJECT_ROOT / "data" / "alliance_duel_messages.json"
).load()


class ContentCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = MessageComposer()

    def test_catalog_contains_five_weekdays_and_six_languages(self) -> None:
        self.assertEqual(set(CATALOG.campaign_days), {1, 2, 3, 4, 5})
        self.assertEqual(
            set(CATALOG.schedule.weekday_to_campaign_day),
            {"sunday", "monday", "tuesday", "wednesday", "thursday"},
        )
        self.assertEqual(
            CATALOG.schedule.language_batches,
            (("en", "ru"), ("de", "uk"), ("pt", "ko")),
        )

    def test_manual_letter_contains_english_and_russian(self) -> None:
        parts = self.composer.compose_manual(
            CATALOG,
            1,
            MessageType.ALLIANCE_MESSAGE,
        )

        self.assertEqual(len(parts), 1)
        self.assertIn("ENGLISH", parts[0].text)
        self.assertIn("RUSSIAN", parts[0].text)

    def test_manual_note_is_three_two_language_messages(self) -> None:
        parts = self.composer.compose_manual(
            CATALOG,
            1,
            MessageType.ALLIANCE_NOTE,
        )

        self.assertEqual(len(parts), 3)
        expected_labels = (
            ("ENGLISH", "RUSSIAN"),
            ("GERMAN", "UKRAINIAN"),
            ("PORTUGUESE", "KOREAN"),
        )
        for part, labels in zip(parts, expected_labels, strict=True):
            for label in labels:
                self.assertIn(label, part.text)

    def test_automatic_schedule_sends_day_one_packet_on_sunday(self) -> None:
        parts = self.composer.compose_scheduled(CATALOG, date(2026, 11, 15))

        self.assertEqual(len(parts), 4)
        self.assertIn("ALLIANCE DUEL | DAY 1", parts[0].text)
        self.assertEqual(
            tuple(part.key for part in parts),
            ("alliance_message", "note_1", "note_2", "note_3"),
        )

    def test_friday_sends_shield_reminder_in_three_language_batches(self) -> None:
        parts = self.composer.compose_scheduled(CATALOG, date(2026, 11, 20))

        self.assertEqual(len(parts), 3)
        self.assertTrue(all("shield_" in part.key for part in parts))
        self.assertIn("Friday to Saturday", parts[0].text)

    def test_saturday_has_no_campaign_delivery(self) -> None:
        self.assertEqual(
            self.composer.compose_scheduled(CATALOG, date(2026, 11, 21)),
            (),
        )


if __name__ == "__main__":
    unittest.main()
