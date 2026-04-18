from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class CardInfo:
    card_no: str
    process_route_code: str | None = None
    alloy_grade: str | None = None
    batch_no: str | None = None
    qr_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CoilSnapshot:
    coil_id: str
    tracking_card_no: str
    qr_code: str | None = None
    batch_no: str | None = None
    contract_no: str | None = None
    workshop_code: str | None = None
    process_code: str | None = None
    machine_code: str | None = None
    shift_code: str | None = None
    status: str | None = None
    event_time: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScheduleItem:
    tracking_card_no: str
    workshop: str
    machine: str | None = None
    shift: str | None = None
    planned_input_weight: float | None = None
    planned_output_weight: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MesAdapter(ABC):
    @abstractmethod
    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        raise NotImplementedError

    @abstractmethod
    def list_coil_snapshots(
        self,
        *,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        limit: int = 200,
    ) -> tuple[list[CoilSnapshot], str | None]:
        raise NotImplementedError

    @abstractmethod
    def get_daily_schedule(self, business_date: date, workshop: str) -> list[ScheduleItem]:
        raise NotImplementedError

    @abstractmethod
    def push_completion(self, card_no: str, output_weight: float | None, yield_rate: float | None) -> bool:
        raise NotImplementedError


class NullMesAdapter(MesAdapter):
    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        return None

    def list_coil_snapshots(
        self,
        *,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        limit: int = 200,
    ) -> tuple[list[CoilSnapshot], str | None]:
        _ = (cursor, updated_after, limit)
        return [], cursor

    def get_daily_schedule(self, business_date: date, workshop: str) -> list[ScheduleItem]:
        return []

    def push_completion(self, card_no: str, output_weight: float | None, yield_rate: float | None) -> bool:
        return False


_mes_adapter: MesAdapter = NullMesAdapter()


def set_mes_adapter(adapter: MesAdapter) -> None:
    global _mes_adapter
    _mes_adapter = adapter


def get_mes_adapter() -> MesAdapter:
    return _mes_adapter
