"""Tests for §4.3 钉钉日报推送 + quality_gate 闸门 (Step 8)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import dingtalk_daily_report


class _FakeDB:
    def __init__(self, report) -> None:
        self.report = report
        self.committed = False
        self._user_query = _UserQuery([])

    def get(self, model, report_id):
        return self.report if (self.report and self.report.id == report_id) else None

    def query(self, *_args, **_kwargs):
        return self._user_query

    def commit(self):
        self.committed = True


class _UserQuery:
    def __init__(self, users):
        self._users = users

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._users)


def _report(*, gate='passed', final='Daily report body'):
    return SimpleNamespace(
        id=99,
        report_date=date(2026, 5, 24),
        report_type='production',
        quality_gate_status=gate,
        quality_gate_summary='3 open recon items' if gate == 'blocked' else None,
        final_text_summary=final,
    )


def _operator():
    return SimpleNamespace(id=1, role='admin')


def test_push_blocked_when_quality_gate_blocked(monkeypatch):
    db = _FakeDB(_report(gate='blocked'))
    monkeypatch.setattr(dingtalk_daily_report, 'record_audit', lambda *_a, **_kw: None)

    with pytest.raises(dingtalk_daily_report.DailyReportPushError, match='quality gate blocked'):
        dingtalk_daily_report.push_daily_report_to_dingtalk(
            db, report_id=99, operator=_operator(),
        )


def test_push_blocked_when_final_summary_empty(monkeypatch):
    db = _FakeDB(_report(final=''))
    monkeypatch.setattr(dingtalk_daily_report, 'record_audit', lambda *_a, **_kw: None)

    with pytest.raises(dingtalk_daily_report.DailyReportPushError, match='final_text_summary is empty'):
        dingtalk_daily_report.push_daily_report_to_dingtalk(
            db, report_id=99, operator=_operator(),
        )


def test_push_blocked_when_report_missing(monkeypatch):
    db = _FakeDB(None)
    with pytest.raises(dingtalk_daily_report.DailyReportPushError, match='report not found'):
        dingtalk_daily_report.push_daily_report_to_dingtalk(
            db, report_id=99, operator=_operator(),
        )


def test_push_sends_to_recipients_when_gate_passed(monkeypatch):
    db = _FakeDB(_report())
    db._user_query = _UserQuery([
        SimpleNamespace(id=10, dingtalk_user_id='dt-10'),
        SimpleNamespace(id=11, dingtalk_user_id='dt-11'),
    ])
    sent: list[tuple[str, str]] = []

    def _send(*, userid, content):
        sent.append((userid, content))
        return True, 'dingtalk_sent'

    monkeypatch.setattr(
        dingtalk_daily_report.dingtalk_service.service,
        'send_work_notification',
        _send,
    )
    monkeypatch.setattr(dingtalk_daily_report, 'record_audit', lambda *_a, **_kw: None)

    result = dingtalk_daily_report.push_daily_report_to_dingtalk(
        db, report_id=99, operator=_operator(),
    )
    assert result == {'sent_count': 2, 'failed': [], 'recipients': 2}
    assert sent == [('dt-10', 'Daily report body'), ('dt-11', 'Daily report body')]
    assert db.committed is True


def test_push_collects_per_user_failures(monkeypatch):
    db = _FakeDB(_report())
    db._user_query = _UserQuery([
        SimpleNamespace(id=10, dingtalk_user_id='dt-10'),
        SimpleNamespace(id=11, dingtalk_user_id='dt-11'),
    ])

    def _send(*, userid, content):
        if userid == 'dt-11':
            return False, 'dingtalk_user_missing'
        return True, 'dingtalk_sent'

    monkeypatch.setattr(
        dingtalk_daily_report.dingtalk_service.service,
        'send_work_notification',
        _send,
    )
    monkeypatch.setattr(dingtalk_daily_report, 'record_audit', lambda *_a, **_kw: None)

    result = dingtalk_daily_report.push_daily_report_to_dingtalk(
        db, report_id=99, operator=_operator(),
    )
    assert result['sent_count'] == 1
    assert result['recipients'] == 2
    assert result['failed'] == [{'user_id': 11, 'reason': 'dingtalk_user_missing'}]
