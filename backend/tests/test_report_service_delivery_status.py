from datetime import date
from types import SimpleNamespace

from app.services import report_service


class FakeQuery:
    def __init__(self, *, all_value=None, scalar_value=None):
        self._all_value = all_value
        self._scalar_value = scalar_value

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_value

    def scalar(self):
        return self._scalar_value


class FakeDB:
    def __init__(self):
        completed_batches = [
            SimpleNamespace(import_type=import_type)
            for import_type in report_service.REQUIRED_IMPORT_TYPES + ("contract_report",)
        ]
        self._queries = [
            FakeQuery(all_value=completed_batches),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=3),
            FakeQuery(scalar_value=2),
            FakeQuery(scalar_value=1),
        ]

    def query(self, *_args, **_kwargs):
        if not self._queries:
            raise AssertionError("unexpected extra query in build_delivery_status")
        return self._queries.pop(0)


def test_build_delivery_status_exposes_split_report_counts(monkeypatch):
    monkeypatch.setattr("app.services.report_service.quality_service.count_open_issues", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr("app.services.report_service.quality_service.count_open_blockers", lambda *_args, **_kwargs: 0)

    payload = report_service.build_delivery_status(FakeDB(), target_date=date(2026, 3, 26))

    assert payload["reports_generated"] == 3
    assert payload["reports_reviewed_count"] == 2
    assert payload["reports_published_count"] == 1
    assert payload["reports_published"] == 3
    assert payload["reports_published_deprecated"] is True
    assert payload["delivery_ready"] is True
