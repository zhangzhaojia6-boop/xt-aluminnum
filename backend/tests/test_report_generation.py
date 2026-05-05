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
