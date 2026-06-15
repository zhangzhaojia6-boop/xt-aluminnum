"""Step 8 — 钉钉日报推送 + quality_gate 闸门.

载荷：`daily_reports.final_text_summary`。
门控：`daily_reports.quality_gate_status == 'blocked'` 时拒绝下发。
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models.agent_communication import ExternalMessageLog
from app.models.reports import DailyReport
from app.models.system import User
from app.services import dingtalk_service
from app.services.audit_service import record_audit


class DailyReportPushError(ValueError):
    """Raised when the daily report cannot be pushed (gate blocked / no body)."""


def _resolve_recipients(
    db: Session,
    *,
    user_ids: Iterable[int] | None,
) -> list[User]:
    query = db.query(User).filter(User.dingtalk_user_id.isnot(None), User.is_active.is_(True))
    if user_ids is not None:
        ids = [int(x) for x in user_ids if x is not None]
        if not ids:
            return []
        query = query.filter(User.id.in_(ids))
    else:
        query = query.filter(User.role.in_(['admin', 'manager']))
    return query.all()


def _normalize_send_detail(detail: str | dict) -> tuple[str, str | None, dict | None]:
    if not isinstance(detail, dict):
        return str(detail or ''), None, None
    text = str(detail.get('detail') or 'dingtalk_send_failed')
    provider_message_id = detail.get('provider_message_id')
    response_payload = detail.get('response_payload')
    return (
        text,
        str(provider_message_id) if provider_message_id not in (None, '') else None,
        response_payload if isinstance(response_payload, dict) else None,
    )


def _write_work_notification_log(
    db: Session,
    *,
    userid: str,
    ok: bool,
    detail: str | dict,
) -> str:
    detail_text, provider_message_id, response_payload = _normalize_send_detail(detail)
    db.add(
        ExternalMessageLog(
            outbox_message_id=None,
            channel_type='dingtalk_work_notification',
            channel_key=userid,
            status='sent' if ok else 'failed',
            detail=detail_text,
            provider_message_id=provider_message_id,
            response_payload=response_payload,
        )
    )
    return detail_text


def push_daily_report_to_dingtalk(
    db: Session,
    *,
    report_id: int,
    operator: User,
    recipient_user_ids: Iterable[int] | None = None,
) -> dict:
    """Push the report's `final_text_summary` to DingTalk users.

    Returns:
        {
          'sent_count': int,
          'failed': list[{'user_id': int, 'reason': str}],
          'recipients': int,
        }

    Raises:
        DailyReportPushError: when the report is missing, the quality gate is
        blocked, or the final summary is empty. The orchestrator must surface
        the message to the caller — the reminder channel should NOT fall back
        to the auto-generated `text_summary`.
    """
    report = db.get(DailyReport, report_id)
    if report is None:
        raise DailyReportPushError('report not found')
    if report.quality_gate_status == 'blocked':
        raise DailyReportPushError(
            f'quality gate blocked: {report.quality_gate_summary or "open reconciliation items"}'
        )
    body = (report.final_text_summary or '').strip()
    if not body:
        raise DailyReportPushError('final_text_summary is empty — finalize the report first')

    recipients = _resolve_recipients(db, user_ids=recipient_user_ids)
    title = f'{report.report_date.isoformat()} 数据中枢日报'
    sent: list[int] = []
    failed: list[dict] = []
    for user in recipients:
        ok, reason = dingtalk_service.service.send_work_notification(
            userid=user.dingtalk_user_id,
            content=body,
        )
        reason_text = _write_work_notification_log(
            db,
            userid=user.dingtalk_user_id,
            ok=ok,
            detail=reason,
        )
        if ok:
            sent.append(user.id)
        else:
            failed.append({'user_id': user.id, 'reason': reason_text})

    record_audit(
        db,
        user=operator,
        action='dingtalk_daily_report_push',
        module='reports',
        entity_type='daily_reports',
        entity_id=report.id,
        detail={
            'report_date': report.report_date.isoformat(),
            'title': title,
            'sent_user_ids': sent,
            'failed': failed,
            'recipients': len(recipients),
        },
        auto_commit=False,
    )
    db.commit()

    return {
        'sent_count': len(sent),
        'failed': failed,
        'recipients': len(recipients),
    }
