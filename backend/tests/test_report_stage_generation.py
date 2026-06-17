from datetime import date
from types import SimpleNamespace

import pytest

from app.models.reports import DailyReport
from app.services.report import report_generation
from app.services.report._utils import PRODUCTION_FORECAST_REPORT_TYPE


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}

    def filter(self, *criteria):
        for criterion in criteria:
            left = getattr(criterion, 'left', None)
            right = getattr(criterion, 'right', None)
            name = getattr(left, 'name', None)
            if name in {'report_date', 'report_type'}:
                self.filters[name] = getattr(right, 'value', None)
        return self

    def first(self):
        for row in self.rows:
            if all(getattr(row, key) == value for key, value in self.filters.items()):
                return row
        return None


class FakeDB:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.added = []
        self.flushed = False
        self.committed = False
        self.refreshed = []

    def query(self, model):
        assert model is DailyReport
        return FakeQuery(self.rows)

    def add(self, entity):
        self.added.append(entity)
        self.rows.append(entity)

    def flush(self):
        self.flushed = True
        for index, entity in enumerate(self.rows, start=1):
            if getattr(entity, 'id', None) is None:
                entity.id = index

    def commit(self):
        self.committed = True

    def refresh(self, entity):
        self.refreshed.append(entity)


def _operator():
    return SimpleNamespace(id=7, role='admin')


def _stub_payload(monkeypatch):
    calls = []

    def fake_generate_report_payload(db, *, report_date, report_type, scope):
        calls.append({'report_date': report_date, 'report_type': report_type, 'scope': scope})
        return {'report_date': report_date.isoformat(), 'total_output_weight': 12.5}, '生产摘要'

    audits = []
    monkeypatch.setattr(report_generation, '_generate_report_payload', fake_generate_report_payload)
    monkeypatch.setattr(report_generation, 'record_audit', lambda *args, **kwargs: audits.append(kwargs))
    return calls, audits


def test_forecast_stage_saves_production_forecast_report(monkeypatch):
    calls, audits = _stub_payload(monkeypatch)
    db = FakeDB()

    reports = report_generation.generate_production_stage_report(
        db,
        report_date=date(2026, 6, 16),
        stage='forecast',
        scope='confirmed_only',
        output_mode='both',
        operator=_operator(),
    )

    assert reports == db.rows
    entity = reports[0]
    assert entity.report_type == PRODUCTION_FORECAST_REPORT_TYPE
    assert entity.report_data['report_stage'] == 'forecast'
    assert entity.report_data['stage_label'] == '07:30预报'
    assert entity.report_data['generated_cutoff_label'] == '07:30预报'
    assert entity.text_summary == '生产摘要'
    assert entity.is_final_version is False
    assert entity.generated_scope == 'auto_confirmed'
    assert entity.output_mode == 'both'
    assert calls == [{'report_date': date(2026, 6, 16), 'report_type': 'production', 'scope': 'auto_confirmed'}]
    assert audits[0]['action'] == 'generate_report_stage'
    assert audits[0]['detail']['report_type'] == PRODUCTION_FORECAST_REPORT_TYPE
    assert audits[0]['detail']['stage'] == 'forecast'


def test_final_stage_updates_production_report_without_resetting_publication(monkeypatch):
    _calls, audits = _stub_payload(monkeypatch)
    existing = DailyReport(
        id=3,
        report_date=date(2026, 6, 16),
        report_type='production',
        report_data={'old': True},
        text_summary='旧摘要',
        status='published',
        reviewed_by=11,
        published_by=12,
        generated_scope='auto_confirmed',
        output_mode='json',
        is_final_version=False,
    )
    db = FakeDB([existing])

    reports = report_generation.generate_production_stage_report(
        db,
        report_date=date(2026, 6, 16),
        stage='final',
        scope='include_reviewed',
        output_mode='both',
        operator=_operator(),
    )

    entity = reports[0]
    assert entity is existing
    assert entity.report_type == 'production'
    assert entity.report_data['report_stage'] == 'final'
    assert entity.report_data['stage_label'] == '09:30终报'
    assert entity.report_data['generated_cutoff_label'] == '09:30终报'
    assert entity.is_final_version is True
    assert entity.final_text_summary == '生产摘要'
    assert entity.status == 'published'
    assert entity.reviewed_by == 11
    assert entity.published_by == 12
    assert audits[0]['detail']['report_type'] == 'production'
    assert audits[0]['detail']['stage'] == 'final'


def test_invalid_stage_raises_value_error():
    db = FakeDB()

    with pytest.raises(ValueError, match='stage must be forecast or final'):
        report_generation.generate_production_stage_report(
            db,
            report_date=date(2026, 6, 16),
            stage='morning',
            scope='auto_confirmed',
            output_mode='both',
            operator=_operator(),
        )

    assert db.committed is False
