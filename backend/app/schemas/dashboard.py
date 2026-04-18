from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.leader_summary import LeaderMetricsOut, LeaderSummaryOut


class FactoryDashboardResponse(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: date | None = None
    leader_summary: LeaderSummaryOut | None = None
    leader_metrics: LeaderMetricsOut | None = None


class WorkshopDashboardResponse(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: date | None = None
    workshop_id: int | None = None
    total_output: float | None = None
    month_to_date_output: float | None = None
    mobile_reporting_summary: dict | None = None
    reminder_summary: dict | None = None
    energy_summary: dict | None = None
    energy_lane: list[dict] | None = None
    inventory_lane: list[dict] | None = None
    exception_lane: dict | None = None
