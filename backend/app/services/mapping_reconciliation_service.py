from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_DIMENSIONS = ('business_date', 'workshop', 'shift')
DEFAULT_REFERENCE_ROOT = Path('D:/输出skill')
FALLBACK_REFERENCE_ROOT = Path('reference/output-skill')
SYSTEM_SOURCES = [
    'mes_stock_records',
    'mes_workshop_process_records',
    'shift_production_data',
    'work_order_entries',
    'daily_consumable_logs',
    'machine_energy_records',
    'data_quality_issues',
    'data_reconciliation_items',
    'daily_reports',
    'workshops',
    'equipment',
    'shift_configs',
]


@dataclass(frozen=True, slots=True)
class MappingFieldSpec:
    metric: str
    reference_field: str
    system_field: str
    reference_unit: str | None = None
    system_unit: str | None = None
    tolerance: float = 0
    weight: float = 1


@dataclass(frozen=True, slots=True)
class MappingDifference:
    reason_code: str
    metric: str
    dimension: dict[str, Any]
    reference_value: float | str | None
    system_value: float | str | None
    diff_value: float | None
    suggested_rule: str


@dataclass(frozen=True, slots=True)
class MappingReconciliationResult:
    total_fields: int
    matched_fields: int
    overall_match_rate: float
    field_match_rates: dict[str, float]
    differences: list[MappingDifference]


def serialize_result(result: MappingReconciliationResult) -> dict[str, Any]:
    return asdict(result)


def _reference_root() -> Path:
    configured = os.getenv('OUTPUT_SKILL_REFERENCE_ROOT')
    if configured:
        return Path(configured)
    if DEFAULT_REFERENCE_ROOT.exists():
        return DEFAULT_REFERENCE_ROOT
    return FALLBACK_REFERENCE_ROOT


def list_sources(*, reference_root: str | Path | None = None, limit: int = 200) -> dict[str, Any]:
    root = Path(reference_root) if reference_root is not None else _reference_root()
    files: list[dict[str, Any]] = []
    if root.exists():
        for item in sorted((path for path in root.rglob('*') if path.is_file()), key=lambda path: str(path))[:limit]:
            files.append(
                {
                    'name': item.name,
                    'relative_path': str(item.relative_to(root)).replace('\\', '/'),
                    'extension': item.suffix.lower(),
                    'size_bytes': item.stat().st_size,
                }
            )
    return {
        'reference_source': str(root),
        'available': root.exists(),
        'files': files,
        'system_sources': SYSTEM_SOURCES,
    }


def _normalize_text(value: Any) -> str:
    return str(value or '').strip().replace(' ', '').replace('（', '(').replace('）', ')')


def _normalize_dimension(
    field: str,
    value: Any,
    aliases: Mapping[str, Mapping[str, str]] | None,
) -> str:
    normalized = _normalize_text(value)
    field_aliases = aliases.get(field, {}) if aliases else {}
    return _normalize_text(field_aliases.get(normalized, normalized))


def _dimension(row: Mapping[str, Any], dimensions: Sequence[str], aliases: Mapping[str, Mapping[str, str]] | None) -> dict[str, Any]:
    return {field: _normalize_dimension(field, row.get(field), aliases) for field in dimensions}


def _dimension_key(dimension: Mapping[str, Any], dimensions: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(dimension.get(field) or '') for field in dimensions)


def _to_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_common_unit(value: Any, unit: str | None) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    normalized_unit = _normalize_text(unit).lower()
    if normalized_unit in {'kg', '公斤', '千克'}:
        return number / 1000
    return number


def _round_rate(value: float) -> float:
    rounded = round(value, 2)
    return int(rounded) if rounded.is_integer() else rounded


def _build_index(
    rows: Iterable[Mapping[str, Any]],
    *,
    dimensions: Sequence[str],
    aliases: Mapping[str, Mapping[str, str]] | None,
) -> dict[tuple[str, ...], Mapping[str, Any]]:
    indexed: dict[tuple[str, ...], Mapping[str, Any]] = {}
    for row in rows:
        dimension = _dimension(row, dimensions, aliases)
        indexed[_dimension_key(dimension, dimensions)] = row
    return indexed


def _value_diff_message(metric: str) -> str:
    return f'检查 {metric} 字段口径、单位或时间范围。'


def compare_mapping_rows(
    *,
    reference_rows: Sequence[Mapping[str, Any]],
    system_rows: Sequence[Mapping[str, Any]],
    fields: Sequence[MappingFieldSpec],
    dimensions: Sequence[str] = DEFAULT_DIMENSIONS,
    dimension_aliases: Mapping[str, Mapping[str, str]] | None = None,
) -> MappingReconciliationResult:
    reference_index = _build_index(reference_rows, dimensions=dimensions, aliases=dimension_aliases)
    system_index = _build_index(system_rows, dimensions=dimensions, aliases=dimension_aliases)

    differences: list[MappingDifference] = []
    matched_fields = 0
    total_fields = 0
    metric_totals: dict[str, float] = {}
    metric_matches: dict[str, float] = {}
    total_weight = 0.0
    matched_weight = 0.0

    for key, reference_row in reference_index.items():
        reference_dimension = _dimension(reference_row, dimensions, dimension_aliases)
        system_row = system_index.get(key)
        if system_row is None:
            for field in fields:
                total_fields += 1
                total_weight += field.weight
                metric_totals[field.metric] = metric_totals.get(field.metric, 0) + field.weight
                differences.append(
                    MappingDifference(
                        reason_code='missing_system_row',
                        metric=field.metric,
                        dimension=reference_dimension,
                        reference_value=reference_row.get(field.reference_field),
                        system_value=None,
                        diff_value=None,
                        suggested_rule='系统侧缺少同日期、车间、班次的数据行。',
                    )
                )
            continue

        for field in fields:
            total_fields += 1
            total_weight += field.weight
            metric_totals[field.metric] = metric_totals.get(field.metric, 0) + field.weight
            reference_value = _to_common_unit(reference_row.get(field.reference_field), field.reference_unit)
            system_value = _to_common_unit(system_row.get(field.system_field), field.system_unit)
            if reference_value is None or system_value is None:
                differences.append(
                    MappingDifference(
                        reason_code='missing_field_value',
                        metric=field.metric,
                        dimension=reference_dimension,
                        reference_value=reference_value,
                        system_value=system_value,
                        diff_value=None,
                        suggested_rule=f'检查 {field.metric} 字段是否缺值或字段名是否映射错误。',
                    )
                )
                continue

            diff_value = round(system_value - reference_value, 6)
            if abs(diff_value) <= field.tolerance:
                matched_fields += 1
                matched_weight += field.weight
                metric_matches[field.metric] = metric_matches.get(field.metric, 0) + field.weight
                continue

            differences.append(
                MappingDifference(
                    reason_code='value_diff',
                    metric=field.metric,
                    dimension=reference_dimension,
                    reference_value=reference_value,
                    system_value=system_value,
                    diff_value=diff_value,
                    suggested_rule=_value_diff_message(field.metric),
                )
            )

    for key, system_row in system_index.items():
        if key in reference_index:
            continue
        system_dimension = _dimension(system_row, dimensions, dimension_aliases)
        differences.append(
            MappingDifference(
                reason_code='extra_system_row',
                metric='dimension',
                dimension=system_dimension,
                reference_value=None,
                system_value=None,
                diff_value=None,
                suggested_rule='系统侧有额外数据行，需确认是否日期、车间、班次别名未对齐。',
            )
        )

    field_match_rates = {
        metric: _round_rate((metric_matches.get(metric, 0) / total) * 100) if total else 0
        for metric, total in metric_totals.items()
    }
    overall_match_rate = _round_rate((matched_weight / total_weight) * 100) if total_weight else 0
    return MappingReconciliationResult(
        total_fields=total_fields,
        matched_fields=matched_fields,
        overall_match_rate=overall_match_rate,
        field_match_rates=field_match_rates,
        differences=differences,
    )


def propose_rules(differences: Sequence[MappingDifference]) -> list[dict[str, Any]]:
    missing = [item for item in differences if item.reason_code == 'missing_system_row']
    extra = [item for item in differences if item.reason_code == 'extra_system_row']
    if not missing or not extra:
        return []

    proposals: list[dict[str, Any]] = []
    missing_dimension = missing[0].dimension
    extra_dimension = extra[0].dimension
    for field in ('workshop', 'shift', 'machine', 'process'):
        reference_value = missing_dimension.get(field)
        system_value = extra_dimension.get(field)
        if reference_value and system_value and reference_value != system_value:
            proposals.append(
                {
                    'rule_type': 'alias_candidate',
                    'field': field,
                    'reference_value': reference_value,
                    'system_value': system_value,
                    'confidence': 'manual_review',
                    'dry_run': True,
                }
            )
    return proposals
