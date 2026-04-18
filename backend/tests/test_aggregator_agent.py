from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.agents.aggregator import AggregatorAgent


class _FakeQuery:
    def __init__(self, *, first=None, scalar=None, all_rows=None):
        self._first = first
        self._scalar = scalar
        self._all_rows = all_rows or []

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def scalar(self):
        return self._scalar

    def all(self):
        return self._all_rows


class _FakeDB:
    def __init__(self, queries: list[_FakeQuery]):
        self._queries = list(queries)
        self.added = []
        self.flushed = 0

    def query(self, *args, **kwargs):
        return self._queries.pop(0)

    def add(self, entity):
        self.added.append(entity)

    def flush(self):
        self.flushed += 1


def _build_default_db() -> _FakeDB:
    workshop_row = SimpleNamespace(
        workshop_id=1,
        total_output_weight=120.0,
        total_input_weight=130.0,
        total_electricity_kwh=500.0,
        total_actual_headcount=18,
    )
    return _FakeDB(
        [
            _FakeQuery(first=None),
            _FakeQuery(scalar=4),
            _FakeQuery(scalar=1),
            _FakeQuery(scalar=2),
            _FakeQuery(scalar=3),
            _FakeQuery(all_rows=[workshop_row]),
            _FakeQuery(all_rows=[SimpleNamespace(id=1, name="铸轧车间")]),
            _FakeQuery(first=None),
        ]
    )


def test_aggregator_skips_when_published_exists() -> None:
    db = _FakeDB([_FakeQuery(first=SimpleNamespace(id=99, status="published"))])
    agent = AggregatorAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert decisions[0].target_id == 99
    assert decisions[0].action.value == "auto_aggregate"


def test_aggregator_skips_when_no_confirmed_data() -> None:
    db = _FakeDB(
        [
            _FakeQuery(first=None),
            _FakeQuery(scalar=0),
            _FakeQuery(scalar=2),
            _FakeQuery(scalar=3),
            _FakeQuery(scalar=2),
        ]
    )
    agent = AggregatorAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert decisions == []


def test_aggregator_generates_and_publishes_report(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.aggregator.settings.AUTO_PUBLISH_ENABLED", True)
    monkeypatch.setattr(
        "app.agents.aggregator.report_service._generate_production_report",
        lambda *args, **kwargs: {
            "ok": True,
            "yield_matrix_lane": {"company_total_yield": 96.0, "quality_status": "ready"},
        },
    )
    monkeypatch.setattr(
        "app.agents.aggregator.report_service._build_boss_text_summary",
        lambda *args, **kwargs: "旧摘要",
    )
    monkeypatch.setattr(
        "app.agents.aggregator.mobile_report_service.summarize_mobile_reporting",
        lambda *args, **kwargs: {"expected_count": 6, "reported_count": 4},
    )
    monkeypatch.setattr(
        "app.agents.aggregator.detect_daily_anomalies",
        lambda *args, **kwargs: {"summary": {"total": 1, "digest": "班次缺报 1条"}, "items": [{"anomaly_type": "shift_missing_report"}]},
    )
    db = _build_default_db()
    agent = AggregatorAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 2
    assert decisions[0].action.value == "auto_aggregate"
    assert decisions[1].action.value == "auto_publish"
    report = db.added[0]
    assert report.status == "published"
    assert report.published_by is None
    assert "生产日报" in report.text_summary
    assert report.report_data["anomaly_summary"]["total"] == 1
    assert report.report_data["yield_matrix_lane"]["company_total_yield"] == 96.0
    assert report.report_data["yield_rate"] == 96.0
    assert report.report_data["yield_rate_source"] == "yield_matrix_lane"


def test_aggregator_generates_without_publish_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.aggregator.settings.AUTO_PUBLISH_ENABLED", False)
    monkeypatch.setattr(
        "app.agents.aggregator.report_service._generate_production_report",
        lambda *args, **kwargs: {"ok": True, "yield_matrix_lane": {}},
    )
    monkeypatch.setattr(
        "app.agents.aggregator.report_service._build_boss_text_summary",
        lambda *args, **kwargs: "旧摘要",
    )
    monkeypatch.setattr(
        "app.agents.aggregator.mobile_report_service.summarize_mobile_reporting",
        lambda *args, **kwargs: {"expected_count": 6, "reported_count": 4},
    )
    monkeypatch.setattr(
        "app.agents.aggregator.detect_daily_anomalies",
        lambda *args, **kwargs: {"summary": {"total": 0, "digest": "未发现关键异常"}, "items": []},
    )
    db = _build_default_db()
    agent = AggregatorAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_aggregate"
    report = db.added[0]
    assert report.status == "reviewed"
    assert report.published_at is None
    assert report.report_data["anomaly_summary"]["total"] == 0


def test_aggregator_always_uses_auto_confirmed_scope(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.aggregator.settings.AUTO_PUBLISH_ENABLED", False)
    calls: list[tuple[str, str]] = []

    def _fake_generate(*args, **kwargs):
        calls.append(("generate", kwargs["scope"]))
        return {"ok": True, "yield_matrix_lane": {}}

    def _fake_summary(*args, **kwargs):
        calls.append(("summary", kwargs["scope"]))
        return "旧摘要"

    monkeypatch.setattr("app.agents.aggregator.report_service._generate_production_report", _fake_generate)
    monkeypatch.setattr("app.agents.aggregator.report_service._build_boss_text_summary", _fake_summary)
    monkeypatch.setattr(
        "app.agents.aggregator.mobile_report_service.summarize_mobile_reporting",
        lambda *args, **kwargs: {"expected_count": 6, "reported_count": 4},
    )
    monkeypatch.setattr(
        "app.agents.aggregator.detect_daily_anomalies",
        lambda *args, **kwargs: {"summary": {"total": 0, "digest": "未发现关键异常"}, "items": []},
    )
    db = _build_default_db()
    agent = AggregatorAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert calls == [("generate", "auto_confirmed"), ("summary", "auto_confirmed")]
    assert db.added[0].generated_scope == "auto_confirmed"


def test_aggregator_does_not_promote_unverified_yield_matrix(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.aggregator.settings.AUTO_PUBLISH_ENABLED", False)
    monkeypatch.setattr(
        "app.agents.aggregator.report_service._generate_production_report",
        lambda *args, **kwargs: {
            "ok": True,
            "yield_matrix_lane": {"company_total_yield": 96.0, "quality_status": "warning"},
        },
    )
    monkeypatch.setattr(
        "app.agents.aggregator.report_service._build_boss_text_summary",
        lambda *args, **kwargs: "旧摘要",
    )
    monkeypatch.setattr(
        "app.agents.aggregator.mobile_report_service.summarize_mobile_reporting",
        lambda *args, **kwargs: {"expected_count": 6, "reported_count": 4},
    )
    monkeypatch.setattr(
        "app.agents.aggregator.detect_daily_anomalies",
        lambda *args, **kwargs: {"summary": {"total": 0, "digest": "未发现关键异常"}, "items": []},
    )
    db = _build_default_db()
    agent = AggregatorAgent()

    agent.execute(db=db, target_date=date(2026, 4, 4))

    report = db.added[0]
    assert report.report_data["yield_rate"] == 92.31
    assert report.report_data["yield_rate_source"] == "runtime_work_order"
