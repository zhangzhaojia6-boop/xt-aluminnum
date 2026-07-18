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


@dataclass(slots=True)
class MesCraft:
    source_id: str
    name: str
    code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MesDevice:
    source_id: str
    name: str
    code: str | None = None
    workshop_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MesStockItem:
    coil_key: str
    tracking_card_no: str
    weight: float | None = None
    destination: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MesWipTotal:
    workshop_name: str
    doing_count: int | None = None
    doing_weight: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MesSourceRecord:
    source_id: str
    source_path: str
    event_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MesMachineLineSource:
    line_code: str
    line_name: str
    workshop_name: str | None = None
    slot_no: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MesAdapter(ABC):
    readonly = False

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

    def list_crafts(self) -> list[MesCraft]:
        raise NotImplementedError('MesAdapter.list_crafts is not implemented for this adapter')

    def list_devices(self) -> list[MesDevice]:
        raise NotImplementedError('MesAdapter.list_devices is not implemented for this adapter')

    def list_follow_cards(self, *, limit: int = 200) -> list[CoilSnapshot]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_follow_cards is not implemented for this adapter')

    def list_dispatch(self, *, limit: int = 200) -> list[CoilSnapshot]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_dispatch is not implemented for this adapter')

    def list_wip_totals(self) -> list[MesWipTotal]:
        raise NotImplementedError('MesAdapter.list_wip_totals is not implemented for this adapter')

    def list_stock(self, *, limit: int = 200) -> list[MesStockItem]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_stock is not implemented for this adapter')

    def list_workshop_process_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_workshop_process_records is not implemented for this adapter')

    def list_workshop_process_records_between(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[MesSourceRecord]:
        _ = (start_at, end_at, limit, offset)
        return []

    def list_stock_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_stock_records is not implemented for this adapter')

    def list_stock_records_between(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[MesSourceRecord]:
        _ = (start_at, end_at, limit, offset)
        return []

    def list_finished_inbound_records_between(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[MesSourceRecord]:
        _ = (start_at, end_at, limit, offset)
        return []

    def list_delivery_records_between(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[MesSourceRecord]:
        _ = (start_at, end_at, limit, offset)
        return []

    def list_material_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_material_records is not implemented for this adapter')

    def list_material_records_between(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[MesSourceRecord]:
        _ = (start_at, end_at, limit, offset)
        return []

    def list_yield_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        _ = limit
        raise NotImplementedError('MesAdapter.list_yield_records is not implemented for this adapter')

    def list_reference_items(self) -> list[MesSourceRecord]:
        raise NotImplementedError('MesAdapter.list_reference_items is not implemented for this adapter')

    def list_machine_line_sources(self) -> list[MesMachineLineSource]:
        raise NotImplementedError('MesAdapter.list_machine_line_sources is not implemented for this adapter')


class NullMesAdapter(MesAdapter):
    readonly = True

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
