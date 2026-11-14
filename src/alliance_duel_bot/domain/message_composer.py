from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from alliance_duel_bot.domain.errors import ContentValidationError
from alliance_duel_bot.domain.models import (
    ContentCatalog,
    DeliveryPart,
    MessageType,
)


LANGUAGE_LABELS = {
    "en": "ENGLISH",
    "ru": "RUSSIAN",
    "de": "GERMAN",
    "uk": "UKRAINIAN",
    "pt": "PORTUGUESE",
    "ko": "KOREAN",
}


class MessageComposer:
    """Builds Telegram-ready message parts from validated campaign content."""

    def compose_manual(
        self,
        catalog: ContentCatalog,
        day_number: int,
        message_type: MessageType,
    ) -> tuple[DeliveryPart, ...]:
        campaign_day = catalog.campaign_days.get(day_number)
        if campaign_day is None:
            raise ContentValidationError(
                f"Campaign Day {day_number} is not available."
            )

        if message_type is MessageType.ALLIANCE_MESSAGE:
            return (
                DeliveryPart(
                    key=MessageType.ALLIANCE_MESSAGE.value,
                    text=self._combine(
                        campaign_day.alliance_message,
                        ("en", "ru"),
                    ),
                ),
            )

        if message_type is MessageType.ALLIANCE_NOTE:
            return self._compose_batches(
                campaign_day.alliance_note,
                catalog.schedule.language_batches,
                key_prefix="note",
            )

        raise ContentValidationError(
            f"Unsupported message type: {message_type!r}."
        )

    def compose_scheduled(
        self, catalog: ContentCatalog, send_date: date
    ) -> tuple[DeliveryPart, ...]:
        schedule = catalog.schedule
        weekday = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )[send_date.weekday()]
        campaign_day_number = schedule.weekday_to_campaign_day.get(weekday)

        if campaign_day_number is not None:
            parts: list[DeliveryPart] = []
            for message_type in schedule.message_order:
                parts.extend(
                    self.compose_manual(catalog, campaign_day_number, message_type)
                )
            return tuple(parts)

        if weekday == "friday" and schedule.friday_action == (
            "send_friday_to_saturday_shield_reminder"
        ):
            return self._compose_batches(
                catalog.friday_shield_reminder,
                schedule.language_batches,
                key_prefix="shield",
            )

        return ()

    def _compose_batches(
        self,
        translations: Mapping[str, str],
        batches: tuple[tuple[str, ...], ...],
        key_prefix: str,
    ) -> tuple[DeliveryPart, ...]:
        return tuple(
            DeliveryPart(
                key=f"{key_prefix}_{index}",
                text=self._combine(translations, languages),
            )
            for index, languages in enumerate(batches, start=1)
        )

    @staticmethod
    def _combine(
        translations: Mapping[str, str],
        languages: tuple[str, ...],
    ) -> str:
        separator = "\n\n" + ("-" * 24) + "\n\n"
        blocks: list[str] = []
        for language in languages:
            text = translations.get(language)
            if not isinstance(text, str) or not text.strip():
                raise ContentValidationError(
                    f"Missing non-empty content for language {language}."
                )
            label = LANGUAGE_LABELS.get(language, language.upper())
            blocks.append(f"{label}\n\n{text.strip()}")
        return separator.join(blocks)
