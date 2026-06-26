from __future__ import annotations

from app.services.hermes_factory_brain_types import FactoryBrainIntent, FactoryBrainNormalizedRequest


_WORKSHOP_ALIASES = {
    '1650冷轧': '1650',
    '1650车间': '1650',
    '1650机组': '1650',
    '1850冷轧': '1850',
    '1850车间': '1850',
    '2050冷轧': '2050',
    '2050车间': '2050',
    '铸轧分厂': 'cast_rolling',
    '铸锭车间': 'casting',
    '热轧车间': 'hot_rolling',
    '退火分厂': 'annealing',
    '精整分厂': 'finishing',
}

_SOURCE_PRIORITY = ['dingtalk_specialist', 'mes', 'wms', 'datahub', 'historical_report', 'rag']


def normalize_factory_request(text: str, intent: FactoryBrainIntent) -> FactoryBrainNormalizedRequest:
    clean = str(text or '').strip()
    org_units = _normalize_org_units(clean, intent)
    metrics = _normalize_metrics(clean, intent)
    needs_artifact = intent.domain == 'artifact' or any(
        token in clean for token in ('表格', '文档', 'PDF', '图表', '图片')
    )
    output_mode = 'artifact' if needs_artifact else _normalize_output_mode(clean)
    return FactoryBrainNormalizedRequest(
        intent=intent,
        normalized_text=clean,
        business_date=intent.business_date,
        scope='workshop' if org_units != ['factory'] else 'factory',
        org_units=org_units,
        metrics=metrics,
        data_sources=list(_SOURCE_PRIORITY),
        output_mode=output_mode,
        needs_artifact=needs_artifact,
    )


def _normalize_org_units(text: str, intent: FactoryBrainIntent) -> list[str]:
    values: list[str] = []
    raw_workshop = str((intent.entities or {}).get('workshop') or '').strip()
    if raw_workshop in _WORKSHOP_ALIASES:
        values.append(_WORKSHOP_ALIASES[raw_workshop])
    for alias, canonical in _WORKSHOP_ALIASES.items():
        if alias in text and canonical not in values:
            values.append(canonical)
    return values or ['factory']


def _normalize_metrics(text: str, intent: FactoryBrainIntent) -> list[str]:
    task = intent.task_type
    if task in {'daily_output', 'daily_report'} or '产量' in text:
        return ['daily_output', 'monthly_output']
    if task == 'factory_overview':
        return ['daily_output', 'inventory', 'contract_balance', 'yield_rate', 'energy_cost', 'anomaly']
    if task == 'inventory_query':
        return ['inventory', 'inbound_finished_goods']
    if task == 'contract_balance':
        return ['contract_balance']
    if task == 'energy_analysis':
        return ['electricity', 'gas', 'unit_consumption']
    if task == 'cost_analysis':
        return ['electricity_cost', 'gas_cost', 'unit_cost']
    if task == 'artifact_request':
        return ['daily_output']
    return [task]


def _normalize_output_mode(text: str) -> str:
    if any(token in text for token in ('日报', '月报', '年报', '正式')):
        return 'formal_report'
    if any(token in text for token in ('分析', '怎么看', '哪里不对劲')):
        return 'analysis'
    return 'short_answer'
