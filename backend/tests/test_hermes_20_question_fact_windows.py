from __future__ import annotations

from app.services.hermes_20_question_acceptance import (
    AcceptanceTurnSnapshot,
    answer_is_confirmed,
    build_20_question_catalog,
    confirmed_fact_failure_reason,
    evaluate_question_snapshot,
)
from app.services.hermes_root_owner_evidence_service import _extract_hub_metric_fact


def _wip_record(*, business_date: str = "2026-11-08", snapshot_at: str = "2026-11-08T08:02:06+08:00") -> dict:
    trace_id = "projection-read:mes_wip_total_snapshots:58:13"
    window = f"{snapshot_at}/{snapshot_at}"
    return {
        "question_id": 10,
        "field": "wip_total",
        "status": "confirmed",
        "value": 1192.0,
        "source_key": "data_hub_projection",
        "source_type": "mes_wip_total_snapshot",
        "source_ref": {
            "source_ref": "mes_wip_total_snapshots",
            "source_table": "mes_wip_total_snapshots",
            "business_date": business_date,
            "business_window": window,
            "unit": "吨",
            "metric_contract_version": "2026-07-11",
            "row_count": 13,
            "latest_row_id": 58,
            "trace_id": trace_id,
        },
        "business_date": business_date,
        "business_window": window,
        "unit": "吨",
        "metric_contract_version": "2026-07-11",
        "trace_id": trace_id,
    }


def _month_record(*, window: str = "2026-11-01T07:50:00+08:00/2026-11-08T07:50:00+08:00") -> dict:
    trace_id = "projection-read:mes_workshop_process_records:36296:947"
    return {
        "question_id": 12,
        "field": "monthly_total_output",
        "status": "confirmed",
        "value": 2500.03,
        "source_key": "data_hub_projection",
        "source_type": "mes_packaging_output",
        "source_ref": {
            "source_ref": "mes_workshop_process_records",
            "source_table": "MES_ProductProcessRecord",
            "business_date": "2026-11-07",
            "business_window": window,
            "unit": "吨",
            "metric_contract_version": "2026-07-11",
            "row_count": 947,
            "latest_row_id": 36296,
            "trace_id": trace_id,
        },
        "business_date": "2026-11-07",
        "business_window": window,
        "unit": "吨",
        "metric_contract_version": "2026-07-11",
        "trace_id": trace_id,
    }


def _snapshot(question_id: int, record: dict, *, business_date: str = "2026-11-07") -> AcceptanceTurnSnapshot:
    question = {item.question_id: item for item in build_20_question_catalog()}[question_id]
    return AcceptanceTurnSnapshot(
        question_id=question_id,
        trace_id=f"trace-q{question_id}",
        status="answered",
        answer="",
        recognition={
            "domain": question.domain,
            "metric_keys": list(question.metric_keys),
            "business_date": business_date,
            "needs_clarification": False,
        },
        evidence={},
        dispatch={},
        source_health={},
        fact_answer=[record],
    )


def _fact_gate(question_id: int, snapshot: AcceptanceTurnSnapshot):
    question = {item.question_id: item for item in build_20_question_catalog()}[question_id]
    return next(gate for gate in evaluate_question_snapshot(question, snapshot).gates if gate.name == "fact")


def test_report_counts_candidate_answers_apart_from_missing_ones() -> None:
    candidate = _snapshot(13, {"field": "annual_total_output", "status": "candidate", "value": 1.0})
    candidate.evidence = {"missing_sources": ["mes_readonly"]}
    missing = _snapshot(13, {"field": "annual_total_output", "status": "missing"})
    question = {item.question_id: item for item in build_20_question_catalog()}[13]

    assert evaluate_question_snapshot(question, candidate).status == "candidate"
    assert evaluate_question_snapshot(question, missing).status == "missing"


def test_wip_snapshot_from_next_morning_is_confirmed_for_the_previous_business_day() -> None:
    record = _wip_record()

    assert answer_is_confirmed(record)
    assert _fact_gate(10, _snapshot(10, record)).passed


def test_wip_snapshot_two_days_later_is_rejected() -> None:
    record = _wip_record(business_date="2026-11-09", snapshot_at="2026-11-09T08:02:06+08:00")

    assert answer_is_confirmed(record)
    assert _fact_gate(10, _snapshot(10, record)).reason == "fact_business_date_mismatch"


def test_snapshot_window_must_fall_on_its_own_date() -> None:
    record = _wip_record(snapshot_at="2026-11-09T08:02:06+08:00")

    assert confirmed_fact_failure_reason(record) == "business_window_contract_mismatch"


def test_point_in_time_window_is_not_accepted_for_a_daily_output_fact() -> None:
    trace_id = "projection-read:mes_workshop_process_records:36296:124"
    instant = "2026-11-07T08:02:06+08:00"
    record = {
        **_month_record(window=f"{instant}/{instant}"),
        "field": "total_output_daily",
        "trace_id": trace_id,
    }
    record["source_ref"] = {**record["source_ref"], "trace_id": trace_id, "row_count": 124}

    assert confirmed_fact_failure_reason(record) == "business_window_contract_mismatch"


def test_month_total_uses_the_packaging_contract_and_a_month_to_date_window() -> None:
    record = _month_record()

    assert answer_is_confirmed(record)
    assert _fact_gate(12, _snapshot(12, record)).passed


def test_month_total_rejects_a_window_that_does_not_start_on_the_first() -> None:
    record = _month_record(window="2026-11-02T07:50:00+08:00/2026-11-08T07:50:00+08:00")

    assert confirmed_fact_failure_reason(record) == "business_window_contract_mismatch"


def test_month_total_rejects_a_window_that_does_not_end_after_the_business_day() -> None:
    record = _month_record(window="2026-11-01T07:50:00+08:00/2026-11-07T07:50:00+08:00")

    assert confirmed_fact_failure_reason(record) == "business_window_contract_mismatch"


def test_hub_reads_month_total_from_the_daily_report_field() -> None:
    fact = {"value": 2500.03, "unit": "吨"}
    payload = {"facts": {"total_output_month": fact, "total_output_daily": {"value": 282.65}}}

    assert _extract_hub_metric_fact(payload, ("monthly_total_output",)) == {"monthly_total_output": fact}
