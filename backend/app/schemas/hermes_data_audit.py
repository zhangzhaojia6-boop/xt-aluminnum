from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class HermesDataAuditRunCreateRequest(BaseModel):
    business_date: date
    fields: list[str] = Field(default_factory=list)
    mes_query_keys: list[str] = Field(default_factory=list)


class HermesDataAuditCorrectionsRequest(BaseModel):
    action_ids: list[int] = Field(default_factory=list)
    idempotency_keys: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = True


class HermesDataAuditDecisionGateOut(BaseModel):
    can_apply: bool
    reason: str
    apply_enabled: bool


class HermesDataAuditSourceHealthItemOut(BaseModel):
    status: str
    row_count: int
    error: Any = None


class HermesDataAuditSourceHealthOut(BaseModel):
    mes: HermesDataAuditSourceHealthItemOut
    hub: HermesDataAuditSourceHealthItemOut
    output_skill: HermesDataAuditSourceHealthItemOut


class HermesDataAuditMatchSummaryOut(BaseModel):
    match_rate: float | None = None
    matched_fields: int
    unmatched_fields: int
    regressed: bool = False


class HermesDataAuditDiffSummaryOut(BaseModel):
    categories: dict[str, int] = Field(default_factory=dict)
    missing_source: int = 0
    cannot_decide: int = 0


class HermesDataAuditCorrectionActionOut(BaseModel):
    id: int | None = None
    idempotency_key: str | None = None
    action_type: str | None = None
    risk_level: str | None = None
    status: str | None = None
    target_table: str | None = None
    target_key: str | None = None
    rollback_available: bool = False


class HermesDataAuditRunEnvelopeOut(BaseModel):
    id: int
    headline_status: str
    business_date: date
    decision_gate: HermesDataAuditDecisionGateOut
    source_health: HermesDataAuditSourceHealthOut
    match_summary: HermesDataAuditMatchSummaryOut
    diff_summary: HermesDataAuditDiffSummaryOut
    correction_actions: list[HermesDataAuditCorrectionActionOut] = Field(default_factory=list)
    recommended_next_step: str


class HermesDataAuditApplySummaryOut(BaseModel):
    audit_run_id: int
    apply_enabled: bool
    reason: str | None = None
    created_count: int = 0
    dry_run_count: int = 0
    applied_count: int = 0
    blocked_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    action_statuses: list[dict[str, Any]] = Field(default_factory=list)


class HermesDataAuditApplyResponseOut(HermesDataAuditRunEnvelopeOut):
    apply_summary: HermesDataAuditApplySummaryOut
