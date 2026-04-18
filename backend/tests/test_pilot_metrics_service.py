from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services.pilot_metrics_service import collect_pilot_metrics


class _FakeQuery:
    def __init__(self, *, all_rows=None, scalar_value=None):
        self._all_rows = all_rows or []
        self._scalar_value = scalar_value

    def filter(self, *args, **kwargs):
        return self

    def with_entities(self, *args, **kwargs):
        return self

    def all(self):
        return self._all_rows

    def scalar(self):
        return self._scalar_value


class _FakeDB:
    def __init__(self, queries: list[_FakeQuery]):
        self._queries = list(queries)

    def query(self, *args, **kwargs):
        return self._queries.pop(0)


def test_collect_pilot_metrics_builds_expected_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.pilot_metrics_service.summarize_mobile_reporting",
        lambda *args, **kwargs: {
            "expected_count": 5,
            "reported_count": 4,
            "returned_count": 1,
            "reporting_rate": 80.0,
            "config_warnings": ["当日应报清单为空"],
        },
    )
    report_rows = [
        SimpleNamespace(
            created_at=datetime(2026, 4, 4, 8, 0, tzinfo=UTC),
            submitted_at=datetime(2026, 4, 4, 8, 10, tzinfo=UTC),
        ),
        SimpleNamespace(
            created_at=datetime(2026, 4, 4, 8, 0, tzinfo=UTC),
            submitted_at=datetime(2026, 4, 4, 8, 30, tzinfo=UTC),
        ),
    ]
    db = _FakeDB(
        [
            _FakeQuery(all_rows=report_rows),
            _FakeQuery(scalar_value=1),
            _FakeQuery(scalar_value=5),
        ]
    )

    payload = collect_pilot_metrics(db, target_date=date(2026, 4, 4))

    assert payload["business_date"] == "2026-04-04"
    assert payload["ttr_minutes_p50"] == 20.0
    assert payload["ttr_minutes_p90"] == 28.0
    assert payload["reporting_rate"] == 80.0
    assert payload["return_rate"] == 25.0
    assert payload["difference_rate"] == 20.0
    assert payload["config_warnings"] == ["当日应报清单为空"]

