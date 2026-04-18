from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MesCoilSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    updated_from_mes_at: datetime | None = None
    last_synced_at: datetime | None = None


class MesSyncStatusOut(BaseModel):
    cursor_key: str
    last_synced_at: datetime | None = None
    last_event_at: datetime | None = None
    lag_seconds: float | None = None
    fetched_count: int = 0
    upserted_count: int = 0
    replayed_count: int = 0
    next_cursor: str | None = None
    status: str = 'idle'
    error_message: str | None = None
