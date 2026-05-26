"""TDD: 钉钉日报推送门控（spec §4.3 / §3.9）.

When `daily_reports.quality_gate_status='blocked'` (any reconciliation_item.status != 'ok'),
ReporterAgent must NOT push the daily report to leaders. Pilot event records skip reason.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.agents import reporter as reporter_module
from app.agents.reporter import ReporterAgent


class _FakeQuery:
    def __init__(self, *, first=None, rows=None):
        self._first = first
        self._rows = rows or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, report, users):
        self._report = report
        self._users = users
        self._called = 0

    def query(self, *args, **kwargs):
        self._called += 1
        if self._called == 1:
            return _FakeQuery(first=self._report)
        return _FakeQuery(rows=self._users)


def _build_report(*, quality_gate_status: str):
    return SimpleNamespace(
        id=99,
        report_date=date(2026, 5, 25),
        report_type="production",
        workshop_id=None,
        generated_scope="confirmed_only",
        output_mode="both",
        status="published",
        quality_gate_status=quality_gate_status,
        report_data={
            "total_output_weight": 180.0,
            "reporting_rate": 96.0,
            "yield_rate": 97.0,
            "total_attendance": 42,
            "anomaly_summary": {"total": 0, "digest": "无"},
        },
        text_summary="日报",
        final_text_summary="最终日报",
        published_by=None,
        published_at=datetime(2026, 5, 25, 8, 0, tzinfo=UTC),
        generated_at=None,
        updated_at=None,
    )


def _build_leaders():
    return [
        SimpleNamespace(id=1, name="厂长", username="admin",
                        dingtalk_user_id="u_admin", role="admin", is_active=True),
    ]


def test_reporter_skips_push_when_quality_gate_blocked(monkeypatch):
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.DINGTALK_ENABLED", False, raising=False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr(
        "app.agents.reporter.report_service.mark_shift_data_published",
        lambda *args, **kwargs: 3,
    )
    monkeypatch.setattr(
        "app.agents.reporter.report_service.resolve_report_delivery_payload",
        lambda *args, **kwargs: {
            "delivery_lane": "yield_matrix_lane",
            "delivery_scope": "factory",
            "delivery_target": "management",
            "delivery_target_key": "management",
            "delivery_resolution_status": "resolved",
            "resolved_targets": [],
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )

    report = _build_report(quality_gate_status='blocked')
    db = _FakeDB(report=report, users=_build_leaders())
    agent = ReporterAgent()

    sent = []
    monkeypatch.setattr(agent, "_send_message",
                        lambda user, content: (sent.append((user, content)) or (True, "sent")))

    decisions = agent.execute(db=db, target_date=date(2026, 5, 25))

    assert sent == []
    assert decisions == []
    assert report.report_data.get("auto_push_blocked_reason") == "quality_gate_blocked"
    assert "auto_push_last_key" not in report.report_data


def test_reporter_pushes_when_quality_gate_passed(monkeypatch):
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.DINGTALK_ENABLED", False, raising=False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr(
        "app.agents.reporter.report_service.mark_shift_data_published",
        lambda *args, **kwargs: 3,
    )
    monkeypatch.setattr(
        "app.agents.reporter.report_service.resolve_report_delivery_payload",
        lambda *args, **kwargs: {
            "delivery_lane": "yield_matrix_lane",
            "delivery_scope": "factory",
            "delivery_target": "management",
            "delivery_target_key": "management",
            "delivery_resolution_status": "resolved",
            "resolved_targets": [],
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )
    monkeypatch.setattr(
        "app.agents.reporter.leader_summary_service.build_best_effort_leader_summary",
        lambda **_kwargs: {
            "summary_text": "摘要",
            "summary_source": "deterministic",
            "metrics": {},
            "llm_enabled": False,
            "llm_error": None,
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.app_connection_service.build_app_connection_payload",
        lambda **_kwargs: {"payload_version": 1, "dispatch_key": "k"},
    )
    monkeypatch.setattr(
        "app.agents.reporter.app_connection_service.dispatch_app_connection_payload",
        lambda **_kwargs: {"status": "dry_run", "detail": "ok"},
    )

    report = _build_report(quality_gate_status='passed')
    db = _FakeDB(report=report, users=_build_leaders())
    agent = ReporterAgent()

    sent = []
    monkeypatch.setattr(agent, "_send_message",
                        lambda user, content: (sent.append((user, content)) or (True, "sent")))

    decisions = agent.execute(db=db, target_date=date(2026, 5, 25))

    assert len(sent) == 1
    assert len(decisions) == 1
    assert "auto_push_last_key" in report.report_data
    assert report.report_data.get("auto_push_blocked_reason") is None


def test_reporter_treats_missing_quality_gate_status_as_passed(monkeypatch):
    """No `quality_gate_status` attribute = legacy report = behave as before."""
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.DINGTALK_ENABLED", False, raising=False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr(
        "app.agents.reporter.report_service.mark_shift_data_published",
        lambda *args, **kwargs: 3,
    )
    monkeypatch.setattr(
        "app.agents.reporter.report_service.resolve_report_delivery_payload",
        lambda *args, **kwargs: {
            "delivery_lane": "yield_matrix_lane",
            "delivery_scope": "factory",
            "delivery_target": "management",
            "delivery_target_key": "management",
            "delivery_resolution_status": "resolved",
            "resolved_targets": [],
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )
    monkeypatch.setattr(
        "app.agents.reporter.leader_summary_service.build_best_effort_leader_summary",
        lambda **_kwargs: {
            "summary_text": "摘要",
            "summary_source": "deterministic",
            "metrics": {},
            "llm_enabled": False,
            "llm_error": None,
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.app_connection_service.build_app_connection_payload",
        lambda **_kwargs: {"payload_version": 1, "dispatch_key": "k"},
    )
    monkeypatch.setattr(
        "app.agents.reporter.app_connection_service.dispatch_app_connection_payload",
        lambda **_kwargs: {"status": "dry_run", "detail": "ok"},
    )

    report = _build_report(quality_gate_status='pending')
    delattr(report, "quality_gate_status")

    db = _FakeDB(report=report, users=_build_leaders())
    agent = ReporterAgent()

    sent = []
    monkeypatch.setattr(agent, "_send_message",
                        lambda user, content: (sent.append((user, content)) or (True, "sent")))

    decisions = agent.execute(db=db, target_date=date(2026, 5, 25))

    assert len(sent) == 1
    assert len(decisions) == 1
