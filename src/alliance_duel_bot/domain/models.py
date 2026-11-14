from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time
from enum import Enum
from zoneinfo import ZoneInfo


class MessageType(str, Enum):
    ALLIANCE_MESSAGE = "alliance_message"
    ALLIANCE_NOTE = "alliance_note"


class DeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CampaignDay:
    number: int
    weekday: str
    alliance_message: Mapping[str, str]
    alliance_note: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class SchedulePolicy:
    timezone: ZoneInfo
    send_time: time
    weekday_to_campaign_day: Mapping[str, int]
    language_batches: tuple[tuple[str, ...], ...]
    message_order: tuple[MessageType, ...]
    friday_action: str
    saturday_action: str
    catchup_grace_minutes: int


@dataclass(frozen=True, slots=True)
class ContentCatalog:
    event_name: str
    campaign_days: Mapping[int, CampaignDay]
    schedule: SchedulePolicy
    friday_shield_reminder: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class DeliveryPart:
    key: str
    text: str


@dataclass(frozen=True, slots=True)
class Subscriber:
    chat_id: int
    full_name: str
    username: str | None = None


@dataclass(frozen=True, slots=True)
class DeliverySummary:
    total_parts: int = 0
    sent_parts: int = 0
    failed_parts: int = 0
    skipped_parts: int = 0

    @property
    def is_successful(self) -> bool:
        return self.failed_parts == 0

    def combine(self, other: DeliverySummary) -> DeliverySummary:
        return DeliverySummary(
            total_parts=self.total_parts + other.total_parts,
            sent_parts=self.sent_parts + other.sent_parts,
            failed_parts=self.failed_parts + other.failed_parts,
            skipped_parts=self.skipped_parts + other.skipped_parts,
        )
