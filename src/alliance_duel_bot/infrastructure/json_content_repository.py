from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import time
from pathlib import Path
from types import MappingProxyType
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from alliance_duel_bot.domain.errors import ContentValidationError
from alliance_duel_bot.domain.models import (
    CampaignDay,
    ContentCatalog,
    MessageType,
    SchedulePolicy,
)
from alliance_duel_bot.domain.ports import ContentRepository


SUPPORTED_LANGUAGES = {"en", "ru", "de", "uk", "pt", "ko"}
CAMPAIGN_WEEKDAYS = {
    1: "monday",
    2: "tuesday",
    3: "wednesday",
    4: "thursday",
    5: "friday",
}
SUPPORTED_SEND_DAYS = {"sunday", "monday", "tuesday", "wednesday", "thursday"}


class JsonContentRepository(ContentRepository):
    """Loads, parses, and validates the project's JSON content catalog."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ContentCatalog:
        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except FileNotFoundError as error:
            raise ContentValidationError(
                f"Content catalog not found: {self.path}"
            ) from error
        except json.JSONDecodeError as error:
            raise ContentValidationError(
                f"Content catalog is not valid JSON: {self.path}"
            ) from error

        root = self._require_mapping(payload, "catalog root")
        self._validate_schema_version(root)
        delivery = self._require_mapping(root.get("delivery"), "delivery")
        automatic = self._require_mapping(
            delivery.get("automatic_schedule"),
            "delivery.automatic_schedule",
        )

        schedule = self._parse_schedule(root, delivery, automatic)
        campaign_days = self._parse_campaign_days(root.get("days"))
        reminder = self._parse_translations(
            root.get("friday_to_saturday_shield_reminder"),
            "friday_to_saturday_shield_reminder",
            SUPPORTED_LANGUAGES,
        )
        event_name = root.get("event")
        if not isinstance(event_name, str) or not event_name.strip():
            raise ContentValidationError("The event name must be a non-empty string.")

        return ContentCatalog(
            event_name=event_name.strip(),
            campaign_days=MappingProxyType(campaign_days),
            schedule=schedule,
            friday_shield_reminder=MappingProxyType(reminder),
        )

    def _parse_schedule(
        self,
        root: Mapping[str, object],
        delivery: Mapping[str, object],
        automatic: Mapping[str, object],
    ) -> SchedulePolicy:
        if delivery.get("destination") != "private_chat":
            raise ContentValidationError(
                "The bot only supports private-chat delivery."
            )

        timezone_name = self._require_string(
            root.get("timezone"),
            "timezone",
        )
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ContentValidationError(
                f"Unknown timezone in content catalog: {timezone_name}."
            ) from error

        send_time_value = self._require_string(
            root.get("send_time_local"),
            "send_time_local",
        )
        try:
            send_time = time.fromisoformat(send_time_value)
        except ValueError as error:
            raise ContentValidationError(
                "send_time_local must use a valid 24-hour time."
            ) from error
        if send_time.tzinfo is not None:
            raise ContentValidationError(
                "send_time_local must be a local wall-clock time without an offset."
            )

        mapping = self._require_mapping(
            automatic.get("send_day_to_content_day"),
            "send_day_to_content_day",
        )
        weekday_mapping: dict[str, int] = {}
        for send_day, campaign_day in mapping.items():
            if send_day not in SUPPORTED_SEND_DAYS:
                raise ContentValidationError(
                    f"Unsupported automatic send day: {send_day}."
                )
            if not isinstance(campaign_day, int) or isinstance(campaign_day, bool):
                raise ContentValidationError(
                    f"Campaign day for {send_day} must be an integer."
                )
            if campaign_day not in CAMPAIGN_WEEKDAYS:
                raise ContentValidationError(
                    f"Unsupported campaign day: {campaign_day}."
                )
            weekday_mapping[send_day] = campaign_day

        expected_mapping = {
            "sunday": 1,
            "monday": 2,
            "tuesday": 3,
            "wednesday": 4,
            "thursday": 5,
        }
        if weekday_mapping != expected_mapping:
            raise ContentValidationError(
                "The automatic schedule must send each campaign day the evening before."
            )

        batches = self._parse_language_batches(
            delivery.get("note_language_batches")
        )
        message_order = self._parse_message_order(delivery.get("message_order"))
        friday_action = automatic.get("friday")
        saturday_action = automatic.get("saturday")
        if friday_action != "send_friday_to_saturday_shield_reminder":
            raise ContentValidationError(
                "Friday must send the Friday-to-Saturday shield reminder."
            )
        if saturday_action != "no_alliance_duel_message":
            raise ContentValidationError(
                "Saturday must be configured without an Alliance Duel message."
            )

        grace = automatic.get("catchup_grace_minutes", 10)
        if not isinstance(grace, int) or isinstance(grace, bool) or grace < 0:
            raise ContentValidationError(
                "catchup_grace_minutes must be a non-negative integer."
            )

        return SchedulePolicy(
            timezone=timezone,
            send_time=send_time,
            weekday_to_campaign_day=MappingProxyType(weekday_mapping),
            language_batches=batches,
            message_order=message_order,
            friday_action=friday_action,
            saturday_action=saturday_action,
            catchup_grace_minutes=grace,
        )

    def _parse_campaign_days(
        self, value: object
    ) -> dict[int, CampaignDay]:
        days = self._require_mapping(value, "days")
        if set(days) != {str(number) for number in range(1, 6)}:
            raise ContentValidationError(
                "The catalog must contain campaign Days 1 through 5."
            )

        campaign_days: dict[int, CampaignDay] = {}
        for number, weekday in CAMPAIGN_WEEKDAYS.items():
            entry = self._require_mapping(days[str(number)], f"days.{number}")
            if entry.get("weekday") != weekday:
                raise ContentValidationError(
                    f"Day {number} must be labeled as {weekday}."
                )

            letter = self._parse_translations(
                entry.get("alliance_message"),
                f"days.{number}.alliance_message",
                {"en", "ru"},
            )
            note = self._parse_translations(
                entry.get("alliance_note"),
                f"days.{number}.alliance_note",
                SUPPORTED_LANGUAGES,
            )
            campaign_days[number] = CampaignDay(
                number=number,
                weekday=weekday,
                alliance_message=MappingProxyType(letter),
                alliance_note=MappingProxyType(note),
            )
        return campaign_days

    def _parse_language_batches(
        self, value: object
    ) -> tuple[tuple[str, ...], ...]:
        if not isinstance(value, list) or not value:
            raise ContentValidationError(
                "note_language_batches must be a non-empty list."
            )
        batches: list[tuple[str, ...]] = []
        for index, batch in enumerate(value, start=1):
            if not isinstance(batch, list) or len(batch) != 2:
                raise ContentValidationError(
                    f"Language batch {index} must contain exactly two languages."
                )
            if any(not isinstance(language, str) for language in batch):
                raise ContentValidationError(
                    f"Language batch {index} contains an invalid language code."
                )
            pair = tuple(batch)
            if len(set(pair)) != 2 or not set(pair) <= SUPPORTED_LANGUAGES:
                raise ContentValidationError(
                    f"Language batch {index} contains duplicate or unsupported languages."
                )
            batches.append(pair)

        flattened = [language for batch in batches for language in batch]
        if set(flattened) != SUPPORTED_LANGUAGES or len(flattened) != len(
            SUPPORTED_LANGUAGES
        ):
            raise ContentValidationError(
                "Language batches must cover each supported language exactly once."
            )
        return tuple(batches)

    @staticmethod
    def _parse_message_order(value: object) -> tuple[MessageType, ...]:
        if not isinstance(value, list):
            raise ContentValidationError("message_order must be a list.")
        try:
            order = tuple(MessageType(item) for item in value)
        except (TypeError, ValueError) as error:
            raise ContentValidationError(
                "message_order contains an unsupported message type."
            ) from error
        if len(order) != 2 or set(order) != set(MessageType):
            raise ContentValidationError(
                "message_order must include each message type exactly once."
            )
        return order

    @staticmethod
    def _parse_translations(
        value: object,
        field_name: str,
        expected_languages: set[str],
    ) -> dict[str, str]:
        translations = JsonContentRepository._require_mapping(value, field_name)
        if set(translations) != expected_languages:
            raise ContentValidationError(
                f"{field_name} must contain exactly: "
                f"{', '.join(sorted(expected_languages))}."
            )
        parsed: dict[str, str] = {}
        for language, text in translations.items():
            if not isinstance(text, str) or not text.strip():
                raise ContentValidationError(
                    f"{field_name}.{language} must be non-empty text."
                )
            parsed[language] = text.strip()
        return parsed

    @staticmethod
    def _validate_schema_version(root: Mapping[str, object]) -> None:
        if root.get("schema_version") != 1:
            raise ContentValidationError(
                "Unsupported content catalog schema version."
            )

    @staticmethod
    def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise ContentValidationError(f"{field_name} must be a JSON object.")
        return value

    @staticmethod
    def _require_string(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ContentValidationError(f"{field_name} must be a non-empty string.")
        return value.strip()
