from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.domain.metric_contracts import daily_report_contract_for
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot
from app.models.system import User
from app.services.report import daily_overview_builder
from app.services.report.daily_report_fact_closure import CRITICAL_DAILY_FACT_FIELDS


SHANGHAI = ZoneInfo("Asia/Shanghai")
TARGET_DATE = date(2026, 7, 7)
BUSINESS_WINDOW = "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00"
FIELD_VALUES = {
    "total_output_daily": 62.0,
    "finished_inbound_daily": 58.5,
    "wip_total": 31.2,
    "total_electricity_kwh": 18420.0,
    "daily_yield_rate": 93.4,
}
FIELD_SOURCES = {
    "total_output_daily": "mes_packaging_output",
    "finished_inbound_daily": "finished_inbound_output",
    "wip_total": "mes_wip_distribution",
    "total_electricity_kwh": "owner_or_energy_summary",
    "daily_yield_rate": "computed_same_basis",
}


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, User.__table__),
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
        ],
    )
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def stub_legacy_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(daily_overview_builder, "_workshop_map", lambda _db: {})
    monkeypatch.setattr(daily_overview_builder, "_build_workshop_output", lambda *_args: [])
    monkeypatch.setattr(daily_overview_builder, "_build_wip_distribution", lambda *_args: [])
    monkeypatch.setattr(
        daily_overview_builder,
        "_build_yield_rates",
        lambda *_args: {"daily": 99.9, "daily_delta": None, "monthly": 99.9},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        "_build_energy",
        lambda *_args: {
            "total_electricity": 99999.0,
            "total_gas": 0.0,
            "electricity_cost": 0.0,
            "gas_cost": 0.0,
            "total_cost": 0.0,
            "by_workshop": [],
        },
    )
    monkeypatch.setattr(
        daily_overview_builder,
        "_build_contracts",
        lambda *_args: {
            "daily_new": 0.0,
            "monthly_total": 0.0,
            "remaining": 0.0,
            "remaining_delta": 0.0,
            "unit": "吨",
        },
    )
    monkeypatch.setattr(
        daily_overview_builder,
        "_build_plant_output",
        lambda *_args: {
            "daily_output": 999.0,
            "yesterday_output": 998.0,
            "monthly_output": 9999.0,
            "finished_inbound_output": 888.0,
            "yield_rate": 99.9,
        },
    )
    monkeypatch.setattr(daily_overview_builder, "_build_shift_breakdown", lambda *_args: {})


def _facts() -> dict[str, dict[str, Any]]:
    return {
        field: {
            "value": FIELD_VALUES[field],
            "unit": daily_report_contract_for(field).unit,
            "source": FIELD_SOURCES[field],
            "source_type": FIELD_SOURCES[field],
            "trace_id": f"trace-{field}",
            "source_detail": {
                "business_window": BUSINESS_WINDOW,
                "trace_id": f"trace-{field}",
            },
        }
        for field in CRITICAL_DAILY_FACT_FIELDS
    }


def _add_snapshot(
    db: Session,
    *,
    reason: str = "scheduled_daily_closure",
    facts: dict[str, Any] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    value_suffix: str = "canonical",
    created_at: datetime | None = None,
    canonical_key: bool | None = None,
) -> DailyFactBundleSnapshot:
    run = DailyFactBundleRun(
        run_key=f"{reason}:{value_suffix}",
        business_date=TARGET_DATE,
        trace_id=f"run-{value_suffix}",
        status="ready",
        source_status={},
    )
    db.add(run)
    db.flush()
    payload_facts = facts if facts is not None else _facts()
    snapshot = DailyFactBundleSnapshot(
        run_id=run.id,
        snapshot_key=(
            f"scheduled_daily_closure:{run.run_key}"
            if canonical_key is True or (canonical_key is None and reason == "scheduled_daily_closure")
            else None
        ),
        business_date=TARGET_DATE,
        snapshot_reason=reason,
        facts=payload_facts,
        sources={
            field: {"source_type": item.get("source_type")}
            for field, item in payload_facts.items()
            if isinstance(item, dict)
        },
        conflicts=conflicts or [],
        adopted_values={
            field: item.get("value")
            for field, item in payload_facts.items()
            if isinstance(item, dict)
        },
        correction_refs=[],
        dingtalk_refs=[],
        output_skill_alignment={},
        payload_hash=f"hash-{value_suffix}",
        trace_id=f"snapshot-{value_suffix}",
        created_at=created_at or datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _overview(db: Session) -> dict[str, Any]:
    return daily_overview_builder.build_daily_production_overview(db, target_date=TARGET_DATE)


def _field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    return next(
        item
        for item in payload["fact_closure"]["critical_fields"]
        if item["field"] == field_name
    )


def test_daily_overview_preserves_latest_canonical_snapshot_fact_contract(db_session: Session) -> None:
    _add_snapshot(db_session)
    db_session.commit()

    payload = _overview(db_session)

    fact = _field(payload, "total_output_daily")
    assert fact == {
        "field": "total_output_daily",
        "value": 62.0,
        "unit": "吨",
        "status": "confirmed",
        "source": "mes_packaging_output",
        "business_window": BUSINESS_WINDOW,
        "trace_id": "trace-total_output_daily",
        "action": fact["action"],
    }
    assert fact["action"]
    assert payload["fact_closure"]["status"] == "pass"
    assert payload["fact_closure_available"] is True
    assert payload["fact_closure_capability"] == {
        "status": "available",
        "agent_failure_audit": "unavailable",
    }


def test_daily_overview_without_snapshot_returns_all_critical_facts_missing(db_session: Session) -> None:
    payload = _overview(db_session)

    assert payload["fact_closure"]["status"] == "blocked"
    assert [item["field"] for item in payload["fact_closure"]["critical_fields"]] == list(
        CRITICAL_DAILY_FACT_FIELDS
    )
    for fact in payload["fact_closure"]["critical_fields"]:
        assert fact["value"] is None
        assert fact["unit"] == daily_report_contract_for(fact["field"]).unit
        assert fact["status"] == "missing"
        assert fact["source"] is None
        assert fact["business_window"] is None
        assert fact["trace_id"] is None
    assert payload["fact_missing"] == []
    assert payload["fact_conflicts"] == []
    assert payload["hermes_failures"] == []
    assert payload["dingtalk_inbound_failures"] == []
    assert payload["fact_closure_available"] is False
    assert payload["fact_closure_capability"] == {
        "status": "missing",
        "agent_failure_audit": "unavailable",
    }


def test_newer_formal_snapshot_never_overrides_canonical_scheduled_snapshot(db_session: Session) -> None:
    canonical_facts = _facts()
    formal_facts = _facts()
    formal_facts["total_output_daily"]["value"] = 999.0
    _add_snapshot(
        db_session,
        facts=canonical_facts,
        value_suffix="canonical-priority",
        created_at=datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI),
    )
    _add_snapshot(
        db_session,
        reason="formal_daily_report",
        facts=formal_facts,
        value_suffix="newer-formal",
        created_at=datetime(2026, 7, 8, 12, 0, tzinfo=SHANGHAI),
    )
    db_session.commit()

    payload = _overview(db_session)

    assert _field(payload, "total_output_daily")["value"] == 62.0


def test_formal_snapshot_is_ignored_when_canonical_snapshot_is_absent(db_session: Session) -> None:
    formal_facts = _facts()
    formal_facts["total_output_daily"]["value"] = 63.5
    _add_snapshot(
        db_session,
        reason="formal_daily_report",
        facts=formal_facts,
        value_suffix="formal-fallback",
    )
    db_session.commit()

    payload = _overview(db_session)

    for fact in payload["fact_closure"]["critical_fields"]:
        assert fact["value"] is None
        assert fact["status"] == "missing"
    assert payload["fact_missing"] == []
    assert payload["fact_conflicts"] == []
    assert payload["hermes_failures"] == []
    assert payload["dingtalk_inbound_failures"] == []
    assert payload["fact_closure_available"] is False
    assert payload["fact_closure_capability"]["status"] == "missing"


def test_scheduled_snapshot_without_canonical_key_is_ignored(db_session: Session) -> None:
    _add_snapshot(
        db_session,
        value_suffix="legacy-unkeyed-scheduled",
        canonical_key=False,
    )
    db_session.commit()

    payload = _overview(db_session)

    assert all(item["status"] == "missing" for item in payload["fact_closure"]["critical_fields"])
    assert payload["fact_missing"] == []


def test_snapshot_conflicts_and_missing_facts_become_fact_alerts(db_session: Session) -> None:
    facts = _facts()
    del facts["total_electricity_kwh"]
    _add_snapshot(
        db_session,
        facts=facts,
        conflicts=[{
            "id": "conflict-output",
            "field": "total_output_daily",
            "status": "mismatch",
            "source": "mes_packaging_output",
            "trace_id": "trace-conflict-output",
        }],
        value_suffix="fact-alerts",
    )
    db_session.commit()

    payload = _overview(db_session)

    assert payload["fact_conflicts"] == [{
        "id": "conflict-output",
        "field": "total_output_daily",
        "status": "mismatch",
        "source": "mes_packaging_output",
        "trace_id": "trace-conflict-output",
        "target_date": TARGET_DATE.isoformat(),
        "summary": "total_output_daily 事实冲突",
        "detail_route": "/manage/alerts?trace_id=trace-conflict-output",
    }]
    assert [item["field"] for item in payload["fact_missing"]] == ["total_electricity_kwh"]
    assert payload["fact_missing"][0]["trace_id"] is None


def test_snapshot_missing_unit_window_or_trace_stays_missing_and_not_confirmed(db_session: Session) -> None:
    facts = _facts()
    facts["total_output_daily"].pop("unit")
    facts["finished_inbound_daily"]["source_detail"].pop("business_window")
    facts["wip_total"].pop("trace_id")
    facts["wip_total"]["source_detail"].pop("trace_id")
    _add_snapshot(db_session, facts=facts, value_suffix="missing-metadata")
    db_session.commit()

    payload = _overview(db_session)

    assert _field(payload, "total_output_daily")["unit"] is None
    assert _field(payload, "finished_inbound_daily")["business_window"] is None
    assert _field(payload, "wip_total")["trace_id"] is None
    for field_name in ("total_output_daily", "finished_inbound_daily", "wip_total"):
        assert _field(payload, field_name)["status"] != "confirmed"


def test_daily_overview_does_not_claim_unavailable_agent_failure_audit(db_session: Session) -> None:
    _add_snapshot(db_session)
    db_session.commit()

    payload = _overview(db_session)

    assert payload["hermes_failures"] == []
    assert payload["dingtalk_inbound_failures"] == []
    assert payload["fact_closure_capability"]["agent_failure_audit"] == "unavailable"


def test_derived_reference_sources_never_reach_manage_fact_or_alert_surfaces(db_session: Session) -> None:
    facts = _facts()
    facts["total_output_daily"].update({
        "source": "output_skill",
        "source_type": "output_skill",
        "evidence_status": "needs_evidence",
    })
    facts["wip_total"].update({
        "source": "invented_unapproved_source",
        "source_type": "invented_unapproved_source",
        "evidence_status": "needs_evidence",
    })
    _add_snapshot(
        db_session,
        facts=facts,
        conflicts=[
            {
                "field": "finished_inbound_daily",
                "status": "mismatch",
                "source": "official_daily_report",
                "trace_id": "trace-reference-source",
            },
            {
                "field": "total_electricity_kwh",
                "status": "mismatch",
                "source": "invented_unapproved_source",
                "trace_id": "trace-unknown-source",
            },
        ],
        value_suffix="derived-source-redaction",
    )
    db_session.commit()

    payload = _overview(db_session)

    fact = _field(payload, "total_output_daily")
    assert fact["value"] == 62.0
    assert fact["status"] == "needs_evidence"
    assert fact["business_window"] == BUSINESS_WINDOW
    assert fact["source"] is None
    assert [item["field"] for item in payload["fact_missing"]] == [
        "total_output_daily",
        "wip_total",
    ]
    assert payload["fact_missing"][0]["source"] is None
    assert _field(payload, "wip_total")["source"] is None
    assert [item["source"] for item in payload["fact_conflicts"]] == [None, None]
    assert "output_skill" not in str(payload["fact_closure"])
    assert "official_daily_report" not in str(payload["fact_conflicts"])
    assert "invented_unapproved_source" not in str(payload["fact_closure"])
    assert "invented_unapproved_source" not in str(payload["fact_conflicts"])
