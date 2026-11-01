from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.domain.daily_report_field_contract import SOURCE_LANE_DATA_HUB_PROJECTION, source_lane_priority
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
# 日报「当天在制料」的各段，不含退火分厂、精整分厂两个小计
OVERVIEW_WIP_FIELDS = (
    ('wip_1650_2050_cold', '1650/2050冷轧'),
    ('wip_1850_cold', '1850冷轧'),
    ('wip_milling', '铣床'),
    ('wip_new_north', '新厂北线'),
    ('wip_new_south', '新厂南线'),
    ('wip_park_anneal', '园区退火'),
    ('wip_straightening', '拉矫'),
    ('wip_finishing', '精整'),
    ('wip_park_finishing', '园区精整'),
    ('wip_hot_plate_shearing', '热轧中厚板剪切'),
    ('wip_coating', '彩涂'),
)
PROJECTION_PRIORITY = source_lane_priority(SOURCE_LANE_DATA_HUB_PROJECTION)


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
        fact = _adopted_fact(facts, field)
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
    wip_source = _overlay_wip(overview, facts)
    if wip_source is not None:
        applied['wip_total'] = wip_source
    if applied:
        overview['fact_overlay'] = applied
    return overview


def _overlay_wip(overview: dict[str, Any], facts: Mapping[str, Mapping[str, Any]]) -> Any:
    # 在制料统计每天被原地覆盖，过去日期只有日报快照里还留着；按目标日次日取在制时和日报一致
    total = _adopted_fact(facts, 'wip_total')
    if total is None or not _default_wip_date(overview):
        return None
    rows = [
        {
            'workshop': label,
            'coil_count': None,
            'total_weight': fact['value'],
            'feeding_weight': None,
            'source_basis': 'daily_fact_snapshot',
            'source_label': '日报口径',
        }
        for field, label in OVERVIEW_WIP_FIELDS
        if (fact := _adopted_fact(facts, field)) is not None and _positive(fact['value'])
    ]
    if rows:
        overview['wip_distribution'] = sorted(rows, key=lambda row: -float(row['total_weight']))
    for kpi in overview.get('header_kpis') or []:
        if kpi.get('key') == 'wip_total':
            kpi['value'] = total['value']
    return total.get('source_type') or total.get('source')


def _default_wip_date(overview: Mapping[str, Any]) -> bool:
    try:
        target_date = date.fromisoformat(str(overview.get('target_date')))
        wip_date = date.fromisoformat(str(overview.get('wip_business_date')))
    except ValueError:
        return False
    return wip_date == target_date + timedelta(days=1)


def overlay_factory_dashboard(dashboard: dict[str, Any], facts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    leader_summary = dashboard.get('leader_summary') if isinstance(dashboard.get('leader_summary'), dict) else {}
    for metrics in (dashboard.get('leader_metrics'), leader_summary.get('metrics')):
        if not isinstance(metrics, dict):
            continue
        for key, field in LEADER_METRIC_FACTS.items():
            fact = _adopted_fact(facts, field)
            if fact is not None:
                metrics[key] = fact['value']
        if _adopted_fact(facts, 'daily_yield_rate') is None and not _positive(metrics.get('yield_rate')):
            metrics['yield_rate'] = None
    if leader_summary.get('summary_source') == 'deterministic' and isinstance(leader_summary.get('metrics'), dict):
        leader_summary['summary_text'] = build_deterministic_leader_summary(metrics=leader_summary['metrics'])
    return dashboard


def _adopted_fact(facts: Mapping[str, Mapping[str, Any]], field: str) -> Mapping[str, Any] | None:
    fact = facts.get(field)
    if fact is None:
        return None
    source = fact.get('source_type') or fact.get('source')
    return fact if source_lane_priority(source) > PROJECTION_PRIORITY else None


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False
