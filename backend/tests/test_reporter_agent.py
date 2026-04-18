from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

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


def _build_report():
    return SimpleNamespace(
        id=88,
        report_date=date(2026, 4, 4),
        report_type="production",
        workshop_id=None,
        generated_scope="confirmed_only",
        output_mode="both",
        status="published",
        report_data={
            "total_output_weight": 180.5,
            "reporting_rate": 96.2,
            "yield_rate": 97.1,
            "total_attendance": 42,
            "anomaly_summary": {"total": 2, "digest": "班次缺报 1条；出勤异常 1条"},
        },
        text_summary="日报摘要",
        final_text_summary="最终版日报摘要",
        published_by=None,
        published_at=datetime(2026, 4, 4, 8, 0, tzinfo=UTC),
        generated_at=None,
        updated_at=None,
    )


def _build_users():
    return [
        SimpleNamespace(id=1, name="厂长", username="admin", dingtalk_user_id="u_admin", role="admin", is_active=True),
        SimpleNamespace(
            id=2,
            name="车间主任",
            username="manager",
            dingtalk_user_id="u_manager",
            role="manager",
            is_active=True,
        ),
    ]


def test_reporter_agent_skips_without_published_report() -> None:
    db = _FakeDB(report=None, users=[])
    agent = ReporterAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert decisions == []


def test_reporter_agent_pushes_to_leaders(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.WECOM_APP_ENABLED", False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.report_service.mark_shift_data_published", lambda *args, **kwargs: 3)
    monkeypatch.setattr(
        "app.agents.reporter.report_service.resolve_report_delivery_payload",
        lambda *args, **kwargs: {
            "delivery_lane": "yield_matrix_lane",
            "delivery_scope": "workshop:cold_roll_1450",
            "delivery_target": "workshop",
            "delivery_target_key": "10",
            "delivery_resolution_status": "resolved",
            "resolved_targets": [{"logical_type": "workshop-observer", "channel_key": "10"}],
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )
    monkeypatch.setattr(
        "app.agents.reporter.leader_summary_service.build_best_effort_leader_summary",
        lambda **_kwargs: {
            "summary_text": "这是领导摘要",
            "summary_source": "deterministic",
            "metrics": {},
            "llm_enabled": False,
            "llm_error": None,
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.app_connection_service.build_app_connection_payload",
        lambda **_kwargs: {"payload_version": 1, "dispatch_key": "report:88:test"},
    )
    monkeypatch.setattr(
        "app.agents.reporter.app_connection_service.dispatch_app_connection_payload",
        lambda **_kwargs: {"status": "dry_run", "detail": "payload_recorded_without_network"},
    )
    sent = []
    report = _build_report()
    db = _FakeDB(report=report, users=_build_users())
    agent = ReporterAgent()
    monkeypatch.setattr(agent, "_send_message", lambda userid, content: (sent.append((userid, content)) or (True, "sent")))

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 2
    assert decisions[0].action.value == "auto_publish"
    assert report.report_data["auto_push_sent_count"] == 2
    assert report.report_data["auto_push_failed_count"] == 0
    assert "auto_push_last_key" in report.report_data
    assert report.report_data["published_shift_count"] == 3
    assert "auto_publish_workflow_key" in report.report_data
    assert report.report_data["delivery_resolution"]["delivery_target"] == "workshop"
    assert report.report_data["leader_summary"]["summary_text"] == "这是领导摘要"
    assert report.report_data["app_connection_delivery"]["status"] == "dry_run"
    assert sent and "这是领导摘要" in sent[0][1]


def test_reporter_agent_prefers_yield_matrix_company_total(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.WECOM_APP_ENABLED", False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.report_service.mark_shift_data_published", lambda *args, **kwargs: 3)
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )
    sent = []
    report = _build_report()
    report.report_data["yield_matrix_lane"] = {"company_total_yield": 94.4, "quality_status": "ready"}
    db = _FakeDB(report=report, users=_build_users())
    agent = ReporterAgent()
    monkeypatch.setattr(agent, "_send_message", lambda userid, content: (sent.append((userid, content)) or (True, "sent")))

    agent.execute(db=db, target_date=date(2026, 4, 4))

    assert sent
    assert "成材率：94.40%" in sent[0][1]


def test_reporter_agent_ignores_unverified_yield_matrix(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.WECOM_APP_ENABLED", False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.report_service.mark_shift_data_published", lambda *args, **kwargs: 3)
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )
    sent = []
    report = _build_report()
    report.report_data["yield_matrix_lane"] = {"company_total_yield": 94.4, "quality_status": "warning"}
    db = _FakeDB(report=report, users=_build_users())
    agent = ReporterAgent()
    monkeypatch.setattr(agent, "_send_message", lambda userid, content: (sent.append((userid, content)) or (True, "sent")))

    agent.execute(db=db, target_date=date(2026, 4, 4))

    assert sent
    assert "成材率：97.10%" in sent[0][1]


def test_reporter_agent_skips_duplicate_push(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.WECOM_APP_ENABLED", False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.report_service.mark_shift_data_published", lambda *args, **kwargs: 3)
    monkeypatch.setattr(
        "app.agents.reporter.report_service.resolve_report_delivery_payload",
        lambda *args, **kwargs: {
            "delivery_lane": "yield_matrix_lane",
            "delivery_scope": "workshop:cold_roll_1450",
            "delivery_target": "workshop",
            "delivery_target_key": "10",
            "delivery_resolution_status": "resolved",
            "resolved_targets": [],
        },
    )
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: {"event_type": event_type, "payload": payload},
    )
    report = _build_report()
    db = _FakeDB(report=report, users=_build_users())
    agent = ReporterAgent()

    first = agent.execute(db=db, target_date=date(2026, 4, 4))
    second = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(first) == 2
    assert second == []


def test_reporter_agent_respects_auto_push_toggle(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", False)
    monkeypatch.setattr("app.agents.reporter.settings.WECOM_APP_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.report_service.mark_shift_data_published", lambda *args, **kwargs: 3)
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
    report = _build_report()
    db = _FakeDB(report=report, users=_build_users())
    agent = ReporterAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 2
    assert "auto_push_last_key" in report.report_data
    assert report.report_data["auto_push_sent_count"] == 2


def test_reporter_agent_skips_auto_workflow_emit_for_manual_publish(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reporter.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.settings.WECOM_APP_ENABLED", False)
    monkeypatch.setattr("app.agents.reporter.settings.WORKFLOW_ENABLED", True)
    monkeypatch.setattr("app.agents.reporter.report_service.mark_shift_data_published", lambda *args, **kwargs: 3)
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
    emitted = []
    monkeypatch.setattr(
        "app.agents.reporter.publish_realtime_event",
        lambda event_type, payload: emitted.append((event_type, payload)),
    )
    report = _build_report()
    report.published_by = 9
    db = _FakeDB(report=report, users=_build_users())
    agent = ReporterAgent()
    monkeypatch.setattr(agent, "_send_message", lambda userid, content: (True, "sent"))

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 2
    assert emitted == []
    assert "auto_publish_workflow_key" not in report.report_data
