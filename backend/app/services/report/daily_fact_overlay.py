from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.leader_summary_service import build_deterministic_leader_summary
from app.services.report.daily_overview_builder import _fmt_delta_label
from app.services.report.daily_report_fact_closure import _latest_daily_fact_snapshot

OVERVIEW_FACT_PATHS = {
    'daily_yield_rate': (('yield_rates', 'daily'), ('plant_output', 'yield_rate')),
    'monthly_yield_rate': (('yield_rates', 'monthly'), ('plant_output', 'monthly_yield_rate')),
    'daily_contract_weight': (('contracts', 'daily_new'),),
    'remaining_contract_weight': (('contracts', 'remaining'),),
    'remaining_contract_delta': (('contracts', 'remaining_delta'),),
}
OVERVIEW_SOURCE_PATHS = {
    'daily_yield_rate': (('yield_rates', 'source'), ('plant_output', 'yield_rate_source')),
    'monthly_yield_rate': (('yield_rates', 'monthly_source'),),
}
OVERVIEW_KPI_FACTS = {
    'daily_yield': 'daily_yield_rate',
    'daily_contracts': 'daily_contract_weight',
    'remaining_contracts': 'remaining_contract_weight',
}
LEADER_METRIC_FACTS = {
    'yield_rate': 'daily_yield_rate',
    'contract_weight': 'daily_contract_weight',
}


def latest_daily_fact_values(db: Session | None, *, target_date: date) -> dict[str, Mapping[str, Any]]:
    if not hasattr(db, 'query'):
        return {}
    snapshot = _latest_daily_fact_snapshot(db, target_date=target_date)
    facts = snapshot.facts if snapshot is not None and isinstance(snapshot.facts, Mapping) else {}
    return {
        str(field): fact
        for field, fact in facts.items()
        if isinstance(fact, Mapping) and fact.get('value') not in (None, '')
    }


def overlay_daily_overview(overview: dict[str, Any], facts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    applied: dict[str, Any] = {}
    for field, paths in OVERVIEW_FACT_PATHS.items():
        fact = facts.get(field)
        if fact is None:
            continue
        source = fact.get('source_type') or fact.get('source')
        for section, key in paths:
            if isinstance(overview.get(section), dict):
                overview[section][key] = fact['value']
        for section, key in OVERVIEW_SOURCE_PATHS.get(field, ()):
            if isinstance(overview.get(section), dict):
                overview[section][key] = source
        applied[field] = source
    for kpi in overview.get('header_kpis') or []:
        field = OVERVIEW_KPI_FACTS.get(kpi.get('key'))
        if field not in applied:
            continue
        kpi['value'] = facts[field]['value']
        if field == 'remaining_contract_weight' and 'remaining_contract_delta' in applied:
            kpi['delta'] = facts['remaining_contract_delta']['value']
            kpi['delta_label'] = _fmt_delta_label(kpi['delta'])
    if applied:
        overview['fact_overlay'] = applied
    return overview


def overlay_factory_dashboard(dashboard: dict[str, Any], facts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    leader_summary = dashboard.get('leader_summary') if isinstance(dashboard.get('leader_summary'), dict) else {}
    for metrics in (dashboard.get('leader_metrics'), leader_summary.get('metrics')):
        if not isinstance(metrics, dict):
            continue
        for key, field in LEADER_METRIC_FACTS.items():
            if field in facts:
                metrics[key] = facts[field]['value']
        if 'daily_yield_rate' not in facts and not _positive(metrics.get('yield_rate')):
            metrics['yield_rate'] = None
    if leader_summary.get('summary_source') == 'deterministic' and isinstance(leader_summary.get('metrics'), dict):
        leader_summary['summary_text'] = build_deterministic_leader_summary(metrics=leader_summary['metrics'])
    return dashboard


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False
