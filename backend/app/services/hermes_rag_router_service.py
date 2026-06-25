from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.hermes_factory_brain import HermesKnowledgeUnit


@dataclass(frozen=True, slots=True)
class RoutedKnowledgeResult:
    domain: str
    object_key: str | None
    metric: str | None
    knowledge_types: list[str]
    units: list[HermesKnowledgeUnit]
    excluded_units: list[HermesKnowledgeUnit]


def route_knowledge_request(db: Session, *, query: str, business_date: date) -> RoutedKnowledgeResult:
    clean = str(query or '').strip()
    object_key = _object_key(clean)
    metric = _metric(clean)
    domain = _domain(clean, metric)
    knowledge_types = _knowledge_types(clean, metric)
    rows = (
        db.query(HermesKnowledgeUnit)
        .filter(HermesKnowledgeUnit.status == 'active')
        .order_by(HermesKnowledgeUnit.id.asc())
        .all()
    )
    excluded = [row for row in rows if row.unit_type == 'daily_fact']
    allowed = [
        row
        for row in rows
        if row.unit_type in knowledge_types and row.unit_type != 'daily_fact' and _matches(row, clean, object_key, metric)
    ]
    return RoutedKnowledgeResult(
        domain=domain,
        object_key=object_key,
        metric=metric,
        knowledge_types=knowledge_types,
        units=allowed,
        excluded_units=excluded,
    )


def _object_key(text: str) -> str | None:
    for value in ('1650', '1850', '2050'):
        if value in text:
            return value
    return None


def _metric(text: str) -> str | None:
    if '吨电耗' in text or '电耗' in text:
        return 'electricity_per_ton'
    if '气耗' in text:
        return 'gas_per_ton'
    if '成品率' in text:
        return 'yield_rate'
    return None


def _domain(text: str, metric: str | None) -> str:
    if metric or any(token in text for token in ('工艺', '质量', '异常')):
        return 'process_quality'
    if any(token in text for token in ('合同', '发货', '库存', '交付')):
        return 'operations'
    return 'production'


def _knowledge_types(text: str, metric: str | None) -> list[str]:
    types: list[str] = []
    if metric:
        types.append('metric')
    if any(token in text for token in ('2050', '1850', '1650', '冷轧', '热轧', '退火')):
        types.append('process')
    if any(token in text for token in ('为什么', '异常', '高', '低')):
        types.append('case')
    return types or ['rule', 'field', 'output_format']


def _matches(unit: HermesKnowledgeUnit, text: str, object_key: str | None, metric: str | None) -> bool:
    haystack = f'{unit.title}\n{unit.content}'
    if unit.unit_type == 'metric' and metric == 'electricity_per_ton' and '电耗' in haystack:
        return True
    if unit.unit_type == 'process' and _contains_any(haystack, ('冷轧', object_key)):
        return True
    if unit.unit_type == 'case' and (object_key is None or object_key in haystack):
        return True
    return any(token in haystack for token in text.split() if token)


def _contains_any(text: str, values: tuple[str | None, ...]) -> bool:
    return any(bool(value) and value in text for value in values)
