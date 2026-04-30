from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings, settings as runtime_settings
from app.models.reports import DailyReport
from app.services.leader_summary_service import build_leader_summary_metrics


def _dispatch_key(report: DailyReport) -> str:
    time_point = (
        getattr(report, 'published_at', None)
        or getattr(report, 'generated_at', None)
        or getattr(report, 'updated_at', None)
    )
    if time_point is None:
        return f'report:{report.id}'
    return f'report:{report.id}:{time_point.isoformat()}'


def build_app_connection_payload(
    *,
    report: DailyReport,
    report_data: dict[str, Any],
    leader_summary_text: str,
    summary_source: str,
) -> dict[str, Any]:
    return {
        'payload_version': 1,
        'dispatch_key': _dispatch_key(report),
        'report_date': report.report_date.isoformat(),
        'metrics': build_leader_summary_metrics(report_date=report.report_date, report_data=report_data),
        'leader_summary': leader_summary_text,
        'delivery_status': {
            'report_id': report.id,
            'status': report.status,
            'generated_scope': report.generated_scope,
        },
        'summary_source': summary_source,
    }


def dispatch_app_connection_payload(
    *,
    payload: dict[str, Any],
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    runtime = settings or runtime_settings
    mode = runtime.app_connection_push_mode_normalized
    result = {
        'status': 'disabled',
        'push_mode': mode,
        'sent_at': datetime.now(timezone.utc).isoformat(),
        'http_status': None,
        'detail': None,
    }

    if not runtime.APP_CONNECTION_ENABLED or mode == 'disabled':
        result['detail'] = 'app_connection_disabled'
        return result
    if mode == 'dry_run':
        result['status'] = 'dry_run'
        result['detail'] = 'payload_recorded_without_network'
        return result

    headers = {
        'Authorization': f'Bearer {runtime.APP_CONNECTION_API_KEY}',
        'Content-Type': 'application/json',
    }
    try:
        if client is None:
            with httpx.Client(timeout=runtime.APP_CONNECTION_TIMEOUT_SECONDS) as session:
                response = session.post(str(runtime.APP_CONNECTION_API_BASE), json=payload, headers=headers)
        else:
            response = client.post(str(runtime.APP_CONNECTION_API_BASE), json=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001
        result['status'] = 'failed'
        result['detail'] = f'{exc.__class__.__name__}: {exc}'
        return result

    result['http_status'] = int(response.status_code)
    if 200 <= response.status_code < 300:
        result['status'] = 'sent'
        result['detail'] = 'app_connection_sent'
    else:
        result['status'] = 'failed'
        result['detail'] = f'app_connection_http_{response.status_code}'
    return result
