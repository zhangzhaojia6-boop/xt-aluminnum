from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

REPORT_SCOPE_PATTERN = '^(auto_confirmed|confirmed_only|include_reviewed)$'


class ReportGenerateRequest(BaseModel):
    report_date: date
    report_type: str | None = Field(default=None, pattern='^(production|attendance|exception)$')
    scope: str = Field(default='auto_confirmed', pattern=REPORT_SCOPE_PATTERN)
    output_mode: str = Field(default='both', pattern='^(json|text|both)$')


class DailyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_date: date
    report_type: str
    workshop_id: int | None = None
    report_data: dict | None = None
    text_summary: str | None = None
    generated_scope: str
    output_mode: str
    status: str
    generated_at: datetime | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    published_by: int | None = None
    published_at: datetime | None = None
    final_text_summary: str | None = None
    final_confirmed_by: int | None = None
    final_confirmed_at: datetime | None = None
    is_final_version: bool = False
    quality_gate_status: str | None = None
    quality_gate_summary: str | None = None
    delivery_ready: bool | None = None
    created_at: datetime
    updated_at: datetime


class ReportGenerateResponse(BaseModel):
    reports: list[DailyReportOut]
    count: int


class ReportActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ReportPipelineRequest(BaseModel):
    report_date: date
    scope: str = Field(default='include_reviewed', pattern=REPORT_SCOPE_PATTERN)
    output_mode: str = Field(default='both', pattern='^(json|text|both)$')
    force: bool = False


class ReportPipelineResponse(BaseModel):
    blocked: bool
    message: str | None = None
    open_reconciliation_count: int = 0
    is_final_version: bool = False
    boss_text_summary: str | None = None
    reports: list[DailyReportOut] = []


class ReportFinalizeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    force: bool = False
