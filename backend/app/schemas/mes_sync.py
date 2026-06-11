from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


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
    configured: bool = False
    migration_ready: bool = True
    adapter: str = 'null'
    source: str = 'local_entry'
    stale_threshold_seconds: float | None = None
    retry_limit: int = 0
    status: str = 'idle'
    last_run_status: str = 'idle'
    action_required: str = 'none'
    required_env: list[str] = Field(default_factory=list)
    error_message: str | None = None


class MesSyncRunOut(BaseModel):
    cursor_key: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: str
    fetched_count: int = 0
    upserted_count: int = 0
    replayed_count: int = 0
    duration_seconds: float | None = None
    lag_seconds: float | None = None
    error_message: str | None = None


class MesSyncRunSummaryOut(BaseModel):
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    running_count: int = 0
    latest_status: str = 'idle'


class MesSyncRunsOut(BaseModel):
    cursor_key: str
    limit: int = 12
    summary: MesSyncRunSummaryOut = Field(default_factory=MesSyncRunSummaryOut)
    items: list[MesSyncRunOut] = Field(default_factory=list)


class MesSupplementReadinessOut(BaseModel):
    business_date: date
    sample_limit: int = 100
    status: str
    coverage: dict = Field(default_factory=dict)
    machine_binding: dict = Field(default_factory=dict)
    material_categories: dict = Field(default_factory=dict)
    window_comparison: dict = Field(default_factory=dict)
    unmatched_devices: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
