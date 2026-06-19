from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.reports import DailyReport
from app.models.system import User
from app.services.report import report_generation


class DummyDB:
    pass


class _FakeReportQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _ExistingReportQuery:
    def __init__(self, report) -> None:
        self.report = report

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.report


class GenerateReportDB:
    def __init__(self) -> None:
        self.added: list[DailyReport] = []
        self.committed = False
        self.refreshed: list[DailyReport] = []

    def query(self, model):
        assert model is DailyReport
        return _FakeReportQuery()

    def add(self, entity):
        self.added.append(entity)

    def flush(self) -> None:
        for index, entity in enumerate(self.added, start=1):
            entity.id = index

    def commit(self) -> None:
        self.committed = True

    def refresh(self, entity) -> None:
        self.refreshed.append(entity)


class ExistingGenerateReportDB(GenerateReportDB):
    def __init__(self, report) -> None:
        super().__init__()
        self.report = report

    def query(self, model):
        assert model is DailyReport
        return _ExistingReportQuery(self.report)


class PipelineDB:
    def __init__(self) -> None:
        self.flushed = False
        self.committed = False
        self.refreshed = []

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def refresh(self, entity) -> None:
        self.refreshed.append(entity)


class FinalizeDB:
    def __init__(self, report: SimpleNamespace) -> None:
        self.report = report
        self.flushed = False
        self.committed = False
        self.refreshed = False

    def get(self, model, report_id: int):
        assert model is DailyReport
        return self.report if report_id == self.report.id else None

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def refresh(self, entity) -> None:
        assert entity is self.report
        self.refreshed = True


def _reviewed_report() -> SimpleNamespace:
    return SimpleNamespace(
        id=21,
        report_date=date(2026, 3, 25),
        report_type='production',
        workshop_id=None,
        status='reviewed',
        text_summary='summary',
        final_text_summary=None,
        report_data={'template_daily_report': {'status': 'ready', 'text': 'summary'}},
        final_confirmed_by=None,
        final_confirmed_at=None,
        is_final_version=False,
        quality_gate_status='pending',
        quality_gate_summary=None,
        delivery_ready=False,
    )


def _operator(*, user_id: int, role: str, is_manager: bool = False, is_reviewer: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        role=role,
        is_manager=is_manager,
        is_reviewer=is_reviewer,
        is_mobile_user=False,
        workshop_id=None,
        team_id=None,
        data_scope_type='all',
        assigned_shift_ids=[],
    )


def _stub_finalize_dependencies(monkeypatch, *, blocker_count: int = 0) -> None:
    monkeypatch.setattr(
        report_generation.quality_service,
        'count_open_blockers',
        lambda db, *, business_date: blocker_count,
    )
    monkeypatch.setattr(
        report_generation.quality_service,
        'blocker_summary',
        lambda db, *, business_date: {'has_blockers': blocker_count > 0, 'open_count': blocker_count},
    )
    monkeypatch.setattr(
        report_generation,
        'build_delivery_status',
        lambda db, *, target_date: {'delivery_ready': True},
        raising=False,
    )
    monkeypatch.setattr(report_generation, 'record_audit', lambda *args, **kwargs: None)


def test_finalize_report_rejects_reviewer_without_manager_authority(monkeypatch) -> None:
    report = _reviewed_report()
    db = FinalizeDB(report)
    _stub_finalize_dependencies(monkeypatch)

    with pytest.raises(ValueError, match='only manager or admin can finalize report'):
        report_generation.finalize_report(
            db,
            report_id=report.id,
            operator=_operator(user_id=3, role='reviewer', is_reviewer=True),
        )

    assert report.final_confirmed_by is None
    assert report.is_final_version is False
    assert db.flushed is False
    assert db.committed is False


def test_finalize_report_allows_manager_without_blockers(monkeypatch) -> None:
    report = _reviewed_report()
    db = FinalizeDB(report)
    _stub_finalize_dependencies(monkeypatch)

    result = report_generation.finalize_report(
        db,
        report_id=report.id,
        operator=_operator(user_id=4, role='manager', is_manager=True),
    )

    assert result is report
    assert report.final_confirmed_by == 4
    assert report.is_final_version is True
    assert report.final_text_summary == 'summary'
    assert report.quality_gate_status == 'passed'
    assert report.delivery_ready is True
    assert db.flushed is True
    assert db.committed is True
    assert db.refreshed is True


def test_finalize_report_keeps_blocker_force_admin_only(monkeypatch) -> None:
    report = _reviewed_report()
    db = FinalizeDB(report)
    _stub_finalize_dependencies(monkeypatch, blocker_count=1)

    with pytest.raises(ValueError, match='only admin can force finalize when blockers exist'):
        report_generation.finalize_report(
            db,
            report_id=report.id,
            operator=_operator(user_id=5, role='manager', is_manager=True),
            force=True,
        )

    assert report.final_confirmed_by is None
    assert report.is_final_version is False
    assert db.flushed is False
    assert db.committed is False


def test_finalize_report_rejects_blocked_template_daily_report(monkeypatch) -> None:
    report = _reviewed_report()
    report.report_data = {'template_daily_report': {'status': 'blocked', 'missing_fields': ['total_output_daily']}}
    report.final_text_summary = '旧日报正文'
    db = FinalizeDB(report)
    _stub_finalize_dependencies(monkeypatch)

    with pytest.raises(ValueError, match='template daily report is blocked'):
        report_generation.finalize_report(
            db,
            report_id=report.id,
            operator=_operator(user_id=4, role='manager', is_manager=True),
        )

    assert report.final_confirmed_by is None
    assert report.is_final_version is False
    assert report.final_text_summary == '旧日报正文'
    assert db.flushed is False
    assert db.committed is False


def test_finalize_report_rejects_missing_template_daily_report(monkeypatch) -> None:
    report = _reviewed_report()
    report.report_data = {}
    db = FinalizeDB(report)
    _stub_finalize_dependencies(monkeypatch)

    with pytest.raises(ValueError, match='template daily report is blocked'):
        report_generation.finalize_report(
            db,
            report_id=report.id,
            operator=_operator(user_id=4, role='manager', is_manager=True),
        )

    assert report.final_confirmed_by is None
    assert report.is_final_version is False
    assert db.flushed is False
    assert db.committed is False


def test_publish_report_rejects_blocked_template_daily_report(monkeypatch) -> None:
    report = _reviewed_report()
    report.report_data = {'template_daily_report': {'status': 'blocked', 'missing_fields': ['total_output_daily']}}
    report.final_text_summary = None
    db = FinalizeDB(report)
    monkeypatch.setattr(
        report_generation,
        'mark_shift_data_published',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('blocked report must not publish shifts')),
    )

    with pytest.raises(ValueError, match='template daily report is blocked'):
        report_generation.publish_report(
            db,
            report_id=report.id,
            operator=_operator(user_id=4, role='manager', is_manager=True),
        )

    assert report.status == 'reviewed'
    assert getattr(report, 'published_at', None) is None
    assert getattr(report, 'published_by', None) is None
    assert db.flushed is False
    assert db.committed is False


def test_publish_report_rejects_missing_template_daily_report(monkeypatch) -> None:
    report = _reviewed_report()
    report.report_data = {}
    db = FinalizeDB(report)
    monkeypatch.setattr(
        report_generation,
        'mark_shift_data_published',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('missing template report must not publish shifts')),
    )

    with pytest.raises(ValueError, match='template daily report is blocked'):
        report_generation.publish_report(
            db,
            report_id=report.id,
            operator=_operator(user_id=4, role='manager', is_manager=True),
        )

    assert report.status == 'reviewed'
    assert getattr(report, 'published_at', None) is None
    assert getattr(report, 'published_by', None) is None
    assert db.flushed is False
    assert db.committed is False


def test_generate_daily_reports_embeds_template_daily_report_when_ready(monkeypatch) -> None:
    db = GenerateReportDB()
    template_text = "6月16日，车间总产量日合计328吨（外加工0吨）比昨日↑22吨，月累计5014吨（外加工月累计270吨）。"

    monkeypatch.setattr(
        report_generation,
        "_generate_report_payload",
        lambda *args, **kwargs: ({"total_output_weight": 100.5}, "旧摘要"),
    )
    monkeypatch.setattr(
        report_generation.template_daily_report,
        "build_template_daily_report_payload",
        lambda db, *, target_date: {
            "status": "ready",
            "text": template_text,
            "missing_fields": [],
            "conflicts": [],
            "sources": {"total_output_daily": {"source_type": "mes_packaging_output"}},
            "hermes_fact_bundle": {
                "target_date": date(2026, 6, 16).isoformat(),
                "source": "template_daily_report_facts",
                "facts": [
                    {
                        "key": "total_output_daily",
                        "label": "车间总产量日合计",
                        "value": 328,
                        "unit": "吨",
                        "group": "opening",
                        "business_date": date(2026, 6, 16).isoformat(),
                        "source": {"source_type": "mes_packaging_output"},
                    }
                ],
                "mes_fact_bundle": {"debug": {"raw": True}},
            },
        },
    )
    monkeypatch.setattr(report_generation, "record_audit", lambda *args, **kwargs: None)

    reports = report_generation.generate_daily_reports(
        db,
        report_date=date(2026, 6, 16),
        report_type="production",
        scope="auto_confirmed",
        output_mode="both",
        operator=_operator(user_id=1, role="admin", is_manager=True),
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.text_summary == template_text
    assert report.final_text_summary == template_text
    assert report.report_data["template_daily_report"]["status"] == "ready"
    assert report.report_data["template_daily_report"]["text"] == template_text
    assert report.report_data["template_daily_report"]["sources"]["total_output_daily"]["source_type"] == "mes_packaging_output"
    stored_bundle = report.report_data["template_daily_report"]["hermes_fact_bundle"]
    assert stored_bundle["facts"][0]["key"] == "total_output_daily"
    assert stored_bundle["facts"][0]["source_type"] == "mes_packaging_output"
    assert "mes_fact_bundle" not in stored_bundle


def test_generate_daily_reports_blocks_template_daily_report_without_final_text(monkeypatch) -> None:
    db = GenerateReportDB()

    monkeypatch.setattr(
        report_generation,
        "_generate_report_payload",
        lambda *args, **kwargs: ({"total_output_weight": 100.5}, "旧摘要"),
    )
    monkeypatch.setattr(
        report_generation.template_daily_report,
        "build_template_daily_report_payload",
        lambda db, *, target_date: {
            "status": "blocked",
            "text": None,
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
            "sources": {},
        },
    )
    monkeypatch.setattr(report_generation, "record_audit", lambda *args, **kwargs: None)

    reports = report_generation.generate_daily_reports(
        db,
        report_date=date(2026, 6, 16),
        report_type="production",
        scope="auto_confirmed",
        output_mode="both",
        operator=_operator(user_id=1, role="admin", is_manager=True),
    )

    report = reports[0]
    assert report.text_summary == "旧摘要"
    assert report.final_text_summary is None
    assert report.report_data["template_daily_report"]["status"] == "blocked"
    assert report.report_data["template_daily_report"]["missing_fields"] == ["total_output_daily"]


def test_generate_daily_reports_resets_existing_final_state_when_template_blocks(monkeypatch) -> None:
    existing = SimpleNamespace(
        id=9,
        report_date=date(2026, 6, 16),
        report_type='production',
        report_data={'template_daily_report': {'status': 'ready', 'text': '旧日报正文'}},
        text_summary='旧日报正文',
        final_text_summary='旧日报正文',
        status='published',
        generated_scope='auto_confirmed',
        output_mode='both',
        generated_at=None,
        reviewed_by=2,
        reviewed_at='2026-06-16T07:50:00Z',
        published_by=3,
        published_at='2026-06-16T08:00:00Z',
        final_confirmed_by=4,
        final_confirmed_at='2026-06-16T08:10:00Z',
        is_final_version=True,
        delivery_ready=True,
    )
    db = ExistingGenerateReportDB(existing)
    monkeypatch.setattr(
        report_generation,
        "_generate_report_payload",
        lambda *args, **kwargs: ({"total_output_weight": 100.5}, "旧摘要"),
    )
    monkeypatch.setattr(
        report_generation.template_daily_report,
        "build_template_daily_report_payload",
        lambda db, *, target_date: {
            "status": "blocked",
            "text": None,
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
            "sources": {},
        },
    )
    monkeypatch.setattr(report_generation, "record_audit", lambda *args, **kwargs: None)

    reports = report_generation.generate_daily_reports(
        db,
        report_date=date(2026, 6, 16),
        report_type="production",
        scope="auto_confirmed",
        output_mode="both",
        operator=_operator(user_id=1, role="admin", is_manager=True),
    )

    assert reports == [existing]
    assert existing.status == 'draft'
    assert existing.final_text_summary is None
    assert existing.final_confirmed_by is None
    assert existing.final_confirmed_at is None
    assert existing.is_final_version is False
    assert existing.delivery_ready is False


def test_run_daily_pipeline_preserves_ready_template_final_text(monkeypatch) -> None:
    db = PipelineDB()
    template_text = "6月16日，车间总产量日合计328吨（外加工0吨）比昨日↑22吨，月累计5014吨（外加工月累计270吨）。"
    report = SimpleNamespace(
        id=9,
        report_date=date(2026, 6, 16),
        report_type="production",
        report_data={"template_daily_report": {"status": "ready", "text": template_text}},
        final_text_summary=template_text,
        is_final_version=False,
        quality_gate_status="pending",
        quality_gate_summary=None,
        delivery_ready=False,
    )

    monkeypatch.setattr(report_generation.quality_service, "count_open_blockers", lambda db, *, business_date: 0)
    monkeypatch.setattr(report_generation.quality_service, "blocker_summary", lambda db, *, business_date: {})
    monkeypatch.setattr(
        report_generation,
        "build_delivery_status",
        lambda db, *, target_date: {"delivery_ready": True},
    )
    monkeypatch.setattr(
        report_generation,
        "generate_daily_reports",
        lambda *args, **kwargs: [report],
    )
    monkeypatch.setattr(report_generation, "_build_boss_text_summary", lambda *args, **kwargs: "旧老板摘要")
    monkeypatch.setattr("app.services.reconciliation_service.count_open_items", lambda db, *, business_date: 0)
    monkeypatch.setattr(report_generation, "record_audit", lambda *args, **kwargs: None)

    blocked, message, _open_count, is_final, boss_text, reports = report_generation.run_daily_pipeline(
        db,
        report_date=date(2026, 6, 16),
        scope="auto_confirmed",
        output_mode="both",
        force=False,
        operator=_operator(user_id=1, role="admin", is_manager=True),
    )

    assert blocked is False
    assert message is None
    assert is_final is True
    assert boss_text == "旧老板摘要"
    assert reports == [report]
    assert report.final_text_summary == template_text


def test_run_daily_pipeline_blocks_template_daily_report_final_text(monkeypatch) -> None:
    db = PipelineDB()
    report = SimpleNamespace(
        id=9,
        report_date=date(2026, 6, 16),
        report_type="production",
        report_data={"template_daily_report": {"status": "blocked", "missing_fields": ["total_output_daily"]}},
        final_text_summary="旧日报正文",
        is_final_version=False,
        quality_gate_status="pending",
        quality_gate_summary=None,
        delivery_ready=True,
    )

    monkeypatch.setattr(report_generation.quality_service, "count_open_blockers", lambda db, *, business_date: 0)
    monkeypatch.setattr(report_generation.quality_service, "blocker_summary", lambda db, *, business_date: {})
    monkeypatch.setattr(
        report_generation,
        "build_delivery_status",
        lambda db, *, target_date: {"delivery_ready": True},
    )
    monkeypatch.setattr(
        report_generation,
        "generate_daily_reports",
        lambda *args, **kwargs: [report],
    )
    monkeypatch.setattr(report_generation, "_build_boss_text_summary", lambda *args, **kwargs: "旧老板摘要")
    monkeypatch.setattr("app.services.reconciliation_service.count_open_items", lambda db, *, business_date: 0)
    monkeypatch.setattr(report_generation, "record_audit", lambda *args, **kwargs: None)

    blocked, message, _open_count, is_final, boss_text, reports = report_generation.run_daily_pipeline(
        db,
        report_date=date(2026, 6, 16),
        scope="auto_confirmed",
        output_mode="both",
        force=False,
        operator=_operator(user_id=1, role="admin", is_manager=True),
    )

    assert blocked is False
    assert message is None
    assert is_final is False
    assert boss_text == "旧老板摘要"
    assert reports == [report]
    assert report.final_text_summary is None
    assert report.delivery_ready is False
    assert report.is_final_version is False


def test_generate_report_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_generate_daily_reports(db, *, report_date, report_type, scope, output_mode, operator):
        assert report_date == date(2026, 3, 25)
        assert report_type == 'production'
        assert scope == 'auto_confirmed'
        assert output_mode == 'both'
        assert operator.id == 1
        return [
            SimpleNamespace(
                id=9,
                report_date=report_date,
                report_type=report_type,
                workshop_id=None,
                report_data={'total_output_weight': 100.5},
                text_summary='summary',
                generated_scope=scope,
                output_mode=output_mode,
                status='draft',
                generated_at=datetime(2026, 3, 25, 8, 0, 0),
                reviewed_by=None,
                reviewed_at=None,
                published_by=None,
                published_at=None,
                created_at=datetime(2026, 3, 25, 8, 0, 0),
                updated_at=datetime(2026, 3, 25, 8, 0, 0),
            )
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reports.report_service.generate_daily_reports', fake_generate_daily_reports)

    response = TestClient(app).post('/api/v1/reports/generate', json={'report_date': '2026-03-25', 'report_type': 'production'})

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 1
    assert body['reports'][0]['id'] == 9
    assert body['reports'][0]['report_type'] == 'production'
    assert body['reports'][0]['report_data']['total_output_weight'] == 100.5

    app.dependency_overrides.clear()
