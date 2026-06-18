from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.business_time import last_completed_production_business_date
from app.core.permissions import assert_manager_dashboard_access, get_current_manager_user
from app.core.rate_limit import enforce_request_rate_limit
from app.core.scope import build_scope_summary
from app.schemas.dashboard import DeliveryStatusOut, FactoryDashboardResponse, WorkshopDashboardResponse
from app.models.system import User
from app.services import report_service
from app.services.report import mes_home_packaging_fact
from scripts.check_statistics_module_ready import inspect_statistics_module_ready

router = APIRouter(tags=['dashboard'])

_REDACTED_EXTERNAL_VALUE = '<redacted>'
_SENSITIVE_KEY_PARTS = ('api_key', 'apikey', 'password', 'secret', 'token', 'credential')
_SECRET_ASSIGNMENT_RE = re.compile(
    r'((?:[A-Z0-9_]*(?:API_KEY|APIKEY|PASSWORD|SECRET|TOKEN|CREDENTIAL)[A-Z0-9_]*)\s*[=:：]\s*)([^；;,\s]+)'
)


def _target_or_last_completed(target_date: date | None) -> date:
    return target_date or last_completed_production_business_date()


def _is_sensitive_key(key: object) -> bool:
    key_text = str(key).lower()
    return any(part in key_text for part in _SENSITIVE_KEY_PARTS)


def _redact_secret_assignments(value: str) -> str:
    return _SECRET_ASSIGNMENT_RE.sub(lambda match: f'{match.group(1)}{_REDACTED_EXTERNAL_VALUE}', value)


def _sanitize_external_readiness_payload(value: Any, *, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_external_readiness_payload(item, parent_key=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_external_readiness_payload(item, parent_key=parent_key) for item in value]
    if isinstance(value, str):
        redacted = _redact_secret_assignments(value)
        if parent_key and _is_sensitive_key(parent_key) and redacted == value:
            return _REDACTED_EXTERNAL_VALUE
        return redacted
    return value


def _ensure_reviewer_or_manager(current_user: User):
    summary = build_scope_summary(current_user)
    if not (summary.is_admin or summary.is_reviewer or summary.is_manager):
        raise HTTPException(status_code=403, detail='Dashboard access denied')
    return summary


def _ensure_global_dashboard_scope(current_user: User):
    summary = _ensure_reviewer_or_manager(current_user)
    if summary.role == 'workshop_director':
        raise HTTPException(status_code=403, detail='Global dashboard requires manager or global review scope')
    if summary.is_admin or summary.is_manager:
        return summary
    if summary.data_scope_type == 'all':
        return summary
    if summary.workshop_id is None and not summary.assigned_shift_ids:
        return summary
    raise HTTPException(status_code=403, detail='Global dashboard requires manager or global review scope')


@router.get('/factory-director', response_model=FactoryDashboardResponse, response_model_exclude_none=True)
def factory_director_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_factory_dashboard(db, target_date=_target_or_last_completed(target_date))


@router.get('/workshop-director', response_model=WorkshopDashboardResponse, response_model_exclude_none=True)
def workshop_director_dashboard(
    request: Request,
    target_date: date | None = None,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    selected_workshop_id = workshop_id or current_user.workshop_id
    summary = assert_manager_dashboard_access(current_user, workshop_id=selected_workshop_id)
    if not summary.is_admin and summary.data_scope_type != 'all':
        if summary.workshop_id is not None and selected_workshop_id != summary.workshop_id:
            raise HTTPException(status_code=403, detail='Dashboard scope denied')
        selected_workshop_id = summary.workshop_id if summary.workshop_id is not None else selected_workshop_id
    return report_service.build_workshop_dashboard(
        db,
        target_date=_target_or_last_completed(target_date),
        workshop_id=selected_workshop_id,
    )


@router.get('/statistics')
def statistics_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_statistics_dashboard(db, target_date=_target_or_last_completed(target_date))


@router.get('/delivery-status', response_model=DeliveryStatusOut, response_model_exclude_none=True)
def delivery_status(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_delivery_status(db, target_date=_target_or_last_completed(target_date))


@router.get('/external-readiness')
def external_readiness(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard_external_readiness', limit=20, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return _sanitize_external_readiness_payload(inspect_statistics_module_ready())


@router.get('/mes-home-reconciliation')
def mes_home_reconciliation(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return mes_home_packaging_fact.build_mes_home_reconciliation(
        db,
        target_date=_target_or_last_completed(target_date),
    )


@router.get('/factory', response_model=FactoryDashboardResponse, response_model_exclude_none=True)
def factory_dashboard_alias(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_factory_dashboard(db, target_date=_target_or_last_completed(target_date))


@router.get('/workshop', response_model=WorkshopDashboardResponse, response_model_exclude_none=True)
def workshop_dashboard_alias(
    request: Request,
    target_date: date | None = None,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    selected_workshop_id = workshop_id or current_user.workshop_id
    summary = assert_manager_dashboard_access(current_user, workshop_id=selected_workshop_id)
    if not summary.is_admin and summary.data_scope_type != 'all':
        if summary.workshop_id is not None and selected_workshop_id != summary.workshop_id:
            raise HTTPException(status_code=403, detail='Dashboard scope denied')
        selected_workshop_id = summary.workshop_id if summary.workshop_id is not None else selected_workshop_id
    return report_service.build_workshop_dashboard(
        db,
        target_date=_target_or_last_completed(target_date),
        workshop_id=selected_workshop_id,
    )


@router.get('/cumulative')
def cumulative_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_cumulative(db, target_date=_target_or_last_completed(target_date))


@router.get('/comparison')
def comparison_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_comparison(db, target_date=_target_or_last_completed(target_date))


@router.get('/timeseries')
def timeseries_dashboard(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    target_date: date | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    safe_days = min(max(int(days or 30), 1), 366)
    effective_end = end_date or target_date or _target_or_last_completed(None)
    effective_start = start_date or (effective_end - timedelta(days=safe_days - 1))
    return report_service.build_timeseries(db, start_date=effective_start, end_date=effective_end)


@router.get('/daily-production')
def daily_production_overview(
    request: Request,
    target_date: date | None = None,
    wip_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    from app.services.report import daily_overview_builder
    return daily_overview_builder.build_daily_production_overview(
        db,
        target_date=_target_or_last_completed(target_date),
        wip_date=wip_date,
    )
