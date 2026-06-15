from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.consumable import DailyConsumableLog
from app.models.energy import MachineEnergyRecord
from app.models.executive import CostDailyResult
from app.models.master import Equipment, Workshop
from app.models.mes import MesStockRecord, MesWorkshopProcessRecord
from app.models.production import MobileShiftReport, ShiftProductionData
from app.models.shift import ShiftConfig


DEFAULT_DIMENSIONS = ('business_date', 'workshop', 'shift')
DEFAULT_REFERENCE_ROOT = Path('D:/输出skill')
FALLBACK_REFERENCE_ROOT = Path('reference/output-skill')
SYSTEM_SOURCES = [
    'mes_stock_records',
    'mes_workshop_process_records',
    'shift_production_data',
    'work_order_entries',
    'daily_consumable_logs',
    'cost_daily_result',
    'machine_energy_records',
    'data_quality_issues',
    'data_reconciliation_items',
    'daily_reports',
    'workshops',
    'equipment',
    'shift_configs',
]
TEXT_EXTENSIONS = {'.txt', '.md', '.log'}
EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
JSON_EXTENSIONS = {'.json'}
JSON_LINES_EXTENSIONS = {'.ndjson'}
SHIFT_NAMES = ('长白班', '小夜班', '大夜班', '白班', '小夜', '大夜')
DATE_RE = re.compile(r'(20\d{2})[年\-/.](\d{1,2})[月\-/.](\d{1,2})日?')
NUMBER_RE = r'([0-9]+(?:\.[0-9]+)?)'
NUMERIC_REFERENCE_FIELDS = {
    'input_tons',
    'output_tons',
    'energy_kwh',
    'scrap_tons',
    'downtime_minutes',
    'quality_issue_count',
    'yield_rate',
    'gas_m3',
    'rolling_oil_per_ton',
    'cost_per_ton',
}
DIFFERENCE_REASON_LABELS = {
    'value_diff': '数值不一致',
    'missing_system_row': '系统缺少同维度数据',
    'extra_system_row': '系统存在额外数据',
    'missing_field_value': '字段值缺失',
}


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


def summarize_differences(differences: Sequence[MappingDifference]) -> dict[str, Any]:
    by_reason_code: dict[str, int] = {}
    by_metric: dict[str, int] = {}
    for item in differences:
        by_reason_code[item.reason_code] = by_reason_code.get(item.reason_code, 0) + 1
        by_metric[item.metric] = by_metric.get(item.metric, 0) + 1
    return {
        'total': len(differences),
        'by_reason_code': by_reason_code,
        'by_metric': by_metric,
        'reason_breakdown': [
            {
                'reason_code': reason_code,
                'label': DIFFERENCE_REASON_LABELS.get(reason_code, reason_code),
                'count': count,
            }
            for reason_code, count in by_reason_code.items()
        ],
    }


def _reference_root() -> Path:
    configured = os.getenv('OUTPUT_SKILL_REFERENCE_ROOT')
    if configured:
        return Path(configured)
    if DEFAULT_REFERENCE_ROOT.exists():
        return DEFAULT_REFERENCE_ROOT
    return FALLBACK_REFERENCE_ROOT


def resolve_reference_file(reference_file: str | Path, *, reference_root: str | Path | None = None) -> Path:
    root = Path(reference_root) if reference_root is not None else _reference_root()
    resolved_root = root.resolve()
    incoming = Path(reference_file)
    candidate = incoming if incoming.is_absolute() else resolved_root / incoming
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError('reference_file must stay inside output skill reference root') from exc
    return resolved_candidate


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


def _to_date_text(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or '').strip()
    if not text:
        return None
    match = DATE_RE.search(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return date(year, month, day).isoformat()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _read_reference_text(path: Path) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding='utf-8', errors='ignore')


def _metric_tons(line: str, labels: Sequence[str]) -> float | None:
    label_pattern = '|'.join(re.escape(label) for label in labels)
    match = re.search(rf'(?:{label_pattern})\s*{NUMBER_RE}\s*(吨|t|T|kg|KG|公斤|千克)?', line)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or '吨').lower()
    if unit in {'kg', '公斤', '千克'}:
        return value / 1000
    return value


def _metric_number(line: str, labels: Sequence[str]) -> float | None:
    label_pattern = '|'.join(re.escape(label) for label in labels)
    match = re.search(rf'(?:{label_pattern})\s*{NUMBER_RE}', line, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _metric_minutes(line: str, labels: Sequence[str]) -> float | None:
    label_pattern = '|'.join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    match = re.search(rf'(?:{label_pattern})\s*{NUMBER_RE}\s*(小时|h|H|分钟|min|MIN)?', line)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2) or '分钟'
    if unit in {'小时', 'h', 'H'}:
        return value * 60
    return value


def _line_workshop_shift(line: str) -> tuple[str | None, str | None]:
    for shift in SHIFT_NAMES:
        if shift in line:
            workshop = line.split(shift, 1)[0].strip(' ：:，,')
            return workshop.replace(' ', '') or None, shift
    return None, None


def _parse_text_rows(path: Path) -> list[dict[str, Any]]:
    content = _read_reference_text(path)
    current_date: str | None = _to_date_text(path.name)
    rows: list[dict[str, Any]] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_date = _to_date_text(line)
        if line_date:
            current_date = line_date

        workshop, shift = _line_workshop_shift(line)
        if not current_date or not workshop or not shift:
            continue

        row: dict[str, Any] = {
            'business_date': current_date,
            'workshop': workshop,
            'shift': shift,
        }
        input_tons = _metric_tons(line, ('投入量', '投入重量', '投料量', '投料', '上机重量', '上机量', 'input_tons'))
        output_tons = _metric_tons(line, ('产量', '下机量', '包装产量', '入库量'))
        energy_kwh = _metric_number(line, ('能耗', '电量', '用电', '总电气', '总用电'))
        scrap_tons = _metric_tons(line, ('废料', '废品', '废料量'))
        downtime_minutes = _metric_minutes(line, ('停机时长', '停机时间', '停机'))
        quality_issue_count = _metric_number(line, ('质量异常', '质量问题', '质量门禁', '异常数'))
        yield_rate = _metric_number(line, ('成材率', '成品率', '良品率', '得率'))
        gas_m3 = _metric_number(line, ('燃气', '用气', '气量', '天然气', 'gas_m3'))
        rolling_oil_per_ton = _metric_number(line, ('轧制油吨耗', '轧制油单吨消耗', '轧制油每吨', 'rolling_oil_per_ton'))
        cost_per_ton = _metric_number(line, ('综合吨成本', '单吨成本', '吨成本', '成本/吨', 'cost_per_ton'))
        if input_tons is not None:
            row['input_tons'] = input_tons
        if output_tons is not None:
            row['output_tons'] = output_tons
        if energy_kwh is not None:
            row['energy_kwh'] = energy_kwh
        if scrap_tons is not None:
            row['scrap_tons'] = scrap_tons
        if downtime_minutes is not None:
            row['downtime_minutes'] = downtime_minutes
        if quality_issue_count is not None:
            row['quality_issue_count'] = quality_issue_count
        if yield_rate is not None:
            row['yield_rate'] = yield_rate
        if gas_m3 is not None:
            row['gas_m3'] = gas_m3
        if rolling_oil_per_ton is not None:
            row['rolling_oil_per_ton'] = rolling_oil_per_ton
        if cost_per_ton is not None:
            row['cost_per_ton'] = cost_per_ton
        if len(row) > 3:
            row['source_file'] = str(path)
            row['source_type'] = 'output_skill_text'
            rows.append(row)
    return rows


def _normalize_header(value: Any) -> str:
    return _normalize_text(value).lower().replace('吨', 'ton').replace('度', 'kwh')


def _excel_field(header: str) -> str | None:
    if header in {'日期', '生产日', '业务日'}:
        return 'business_date'
    if header in {'车间', '部门', '工厂'}:
        return 'workshop'
    if header == '班次':
        return 'shift'
    if header in {'机台', '机列', '设备', '设备名称', '设备名'}:
        return 'machine'
    if header in {'工序', '工艺', '当前工艺'}:
        return 'process'
    if header in {'卷号', '随行卡号', '随行卡', '卡号', '批号'}:
        return 'coil_no'
    if header in {'合同号', '合同', '合同编号'}:
        return 'contract_no'
    if header in {'客户', '客户名', '客户名称'}:
        return 'customer'
    if (
        '投入' in header
        or '投料' in header
        or '上机' in header
        or '来料' in header
        or 'input_tons' in header
    ):
        return 'input_tons'
    if '能耗' in header or '电量' in header or 'kwh' in header:
        return 'energy_kwh'
    if '燃气' in header or '用气' in header or '气量' in header or '天然气' in header or 'gas_m3' in header:
        return 'gas_m3'
    if '废料' in header or '废品' in header:
        return 'scrap_tons'
    if '停机' in header:
        return 'downtime_minutes'
    if '质量异常' in header or '质量问题' in header or '异常数' in header or 'quality' in header:
        return 'quality_issue_count'
    if '成材率' in header or '成品率' in header or '良品率' in header or '得率' in header or 'yield' in header:
        return 'yield_rate'
    if '轧制油' in header and (
        '吨耗' in header or 'ton耗' in header or '单吨' in header or '单ton' in header or '每吨' in header or '每ton' in header
    ):
        return 'rolling_oil_per_ton'
    if 'rolling_oil_per_ton' in header:
        return 'rolling_oil_per_ton'
    if '成本' in header and (
        'ton' in header or '单ton' in header or '每ton' in header or '元/ton' in header or 'cost_per_ton' in header
    ):
        return 'cost_per_ton'
    if 'cost_per_ton' in header:
        return 'cost_per_ton'
    if '产量' in header or '下机量' in header or '入库量' in header or '包装' in header:
        return 'output_tons'
    return None


def _normalize_reference_number(field: str, value: Any) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    if field == 'yield_rate' and 0 < number <= 1:
        return round(number * 100, 6)
    return number


def _parse_excel_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == '.xls':
        return _parse_xls_rows(path)

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    headers = next(rows_iter, None)
    if not headers:
        return []

    field_by_index = {
        index: field
        for index, header in enumerate(headers)
        if (field := _excel_field(_normalize_header(header))) is not None
    }
    parsed_rows: list[dict[str, Any]] = []
    for values in rows_iter:
        row: dict[str, Any] = {}
        for index, value in enumerate(values):
            field = field_by_index.get(index)
            if not field or value in (None, ''):
                continue
            if field == 'business_date':
                row[field] = _to_date_text(value)
            elif field in NUMERIC_REFERENCE_FIELDS:
                number = _normalize_reference_number(field, value)
                if number is not None:
                    row[field] = number
            else:
                row[field] = str(value).strip()
        if row.get('business_date') and row.get('workshop') and row.get('shift'):
            row['source_file'] = str(path)
            row['source_type'] = 'output_skill_excel'
            parsed_rows.append(row)
    workbook.close()
    return parsed_rows


def _parse_xls_rows(path: Path) -> list[dict[str, Any]]:
    import xlrd

    workbook = xlrd.open_workbook(str(path))
    sheet = workbook.sheet_by_index(0)
    if sheet.nrows < 1:
        return []

    headers = sheet.row_values(0)
    field_by_index = {
        index: field
        for index, header in enumerate(headers)
        if (field := _excel_field(_normalize_header(header))) is not None
    }
    parsed_rows: list[dict[str, Any]] = []
    for row_index in range(1, sheet.nrows):
        row: dict[str, Any] = {}
        for index, value in enumerate(sheet.row_values(row_index)):
            field = field_by_index.get(index)
            if not field or value in (None, ''):
                continue
            if field == 'business_date':
                cell = sheet.cell(row_index, index)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    row[field] = xlrd.xldate.xldate_as_datetime(value, workbook.datemode).date().isoformat()
                else:
                    row[field] = _to_date_text(value)
            elif field in NUMERIC_REFERENCE_FIELDS:
                number = _normalize_reference_number(field, value)
                if number is not None:
                    row[field] = number
            else:
                row[field] = str(value).strip()
        if row.get('business_date') and row.get('workshop') and row.get('shift'):
            row['source_file'] = str(path)
            row['source_type'] = 'output_skill_excel'
            parsed_rows.append(row)
    return parsed_rows


def _json_reference_records(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for key in ('rows', 'items', 'data', 'records'):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
        return [payload]
    return []


def _json_record_rows(records: Iterable[Mapping[str, Any]], *, path: Path, source_type: str) -> list[dict[str, Any]]:
    default_date = _to_date_text(path.name)
    parsed_rows: list[dict[str, Any]] = []
    for item in records:
        row: dict[str, Any] = {}
        for header, value in item.items():
            field = _excel_field(_normalize_header(header))
            if not field or value in (None, ''):
                continue
            if field == 'business_date':
                row[field] = _to_date_text(value)
            elif field in NUMERIC_REFERENCE_FIELDS:
                number = _normalize_reference_number(field, value)
                if number is not None:
                    row[field] = number
            else:
                row[field] = str(value).strip()
        if not row.get('business_date') and default_date:
            row['business_date'] = default_date
        if row.get('business_date') and row.get('workshop') and row.get('shift'):
            row['source_file'] = str(path)
            row['source_type'] = source_type
            parsed_rows.append(row)
    return parsed_rows


def _parse_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(_read_reference_text(path))
    return _json_record_rows(_json_reference_records(payload), path=path, source_type='output_skill_json')


def _parse_json_lines_rows(path: Path) -> list[dict[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for line in _read_reference_text(path).splitlines():
        text = line.strip()
        if not text:
            continue
        payload = json.loads(text)
        if isinstance(payload, Mapping):
            records.append(payload)
    return _json_record_rows(records, path=path, source_type='output_skill_json_lines')


def parse_output_skill_reference_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        rows = _parse_text_rows(path)
        source_type = 'output_skill_text'
    elif suffix in EXCEL_EXTENSIONS:
        rows = _parse_excel_rows(path)
        source_type = 'output_skill_excel'
    elif suffix in JSON_EXTENSIONS:
        rows = _parse_json_rows(path)
        source_type = 'output_skill_json'
    elif suffix in JSON_LINES_EXTENSIONS:
        rows = _parse_json_lines_rows(path)
        source_type = 'output_skill_json_lines'
    else:
        return {
            'status': 'unsupported',
            'source_file': str(path),
            'source_type': 'unsupported',
            'rows': [],
            'issues': [{'code': 'unsupported_extension', 'extension': suffix}],
        }
    return {
        'status': 'parsed',
        'source_file': str(path),
        'source_type': source_type,
        'rows': rows,
        'issues': [],
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
    if isinstance(value, Decimal):
        return float(value)
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


def _tons_from_pair(tons: Any, kg: Any) -> float | None:
    tons_value = _to_float(tons)
    if tons_value is not None:
        return tons_value
    kg_value = _to_float(kg)
    if kg_value is None:
        return None
    return kg_value / 1000


def _shift_production_weight_tons(record: ShiftProductionData, field_name: str) -> float | None:
    value = _to_float(getattr(record, field_name, None))
    if value is None:
        return None
    if record.data_source == 'mobile_coil_agg':
        return value / 1000
    return value


def _consumable_payload_metrics(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    known_metrics = {
        'packaging_inbound_output_tons',
        'electricity_daily',
        'gas_daily',
    }
    return {
        key: _to_float(value)
        for key, value in payload.items()
        if key not in known_metrics and _to_float(value) is not None
    }


def build_system_mapping_rows(db: Session, *, business_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    shift_rows = (
        db.query(ShiftProductionData, Workshop, ShiftConfig, Equipment)
        .join(Workshop, ShiftProductionData.workshop_id == Workshop.id)
        .join(ShiftConfig, ShiftProductionData.shift_config_id == ShiftConfig.id)
        .outerjoin(Equipment, ShiftProductionData.equipment_id == Equipment.id)
        .filter(
            ShiftProductionData.business_date == business_date,
            ShiftProductionData.data_status != 'voided',
        )
        .order_by(ShiftProductionData.id.asc())
        .all()
    )
    for record, workshop, shift, equipment in shift_rows:
        rows.append(
            {
                'business_date': record.business_date.isoformat(),
                'workshop': workshop.name,
                'shift': shift.name,
                'process': '班次产量',
                'machine': equipment.name if equipment else '',
                'machine_code': equipment.code if equipment else '',
                'input_tons': _shift_production_weight_tons(record, 'input_weight'),
                'output_tons': _shift_production_weight_tons(record, 'output_weight'),
                'scrap_tons': _shift_production_weight_tons(record, 'scrap_weight'),
                'downtime_minutes': _to_float(record.downtime_minutes),
                'quality_issue_count': _to_float(record.issue_count),
                'energy_kwh': _to_float(record.electricity_kwh),
                'source_table': 'shift_production_data',
            }
        )

    process_records = (
        db.query(MesWorkshopProcessRecord)
        .filter(MesWorkshopProcessRecord.business_date == business_date)
        .order_by(MesWorkshopProcessRecord.id.asc())
        .all()
    )
    for record in process_records:
        rows.append(
            {
                'business_date': business_date.isoformat(),
                'workshop': record.workshop_name or '',
                'shift': '',
                'process': record.process_name or '',
                'machine': record.device_name or '',
                'coil_no': record.batch_no or '',
                'input_tons': _tons_from_pair(record.input_weight_tons, record.input_weight_kg),
                'output_tons': _tons_from_pair(record.output_weight_tons, record.output_weight_kg),
                'yield_rate': _to_float(record.yield_rate),
                'source_table': 'mes_workshop_process_records',
            }
        )

    stock_records = (
        db.query(MesStockRecord)
        .filter(MesStockRecord.business_date == business_date)
        .order_by(MesStockRecord.id.asc())
        .all()
    )
    for record in stock_records:
        rows.append(
            {
                'business_date': business_date.isoformat(),
                'workshop': '成品库',
                'shift': '',
                'process': '入库',
                'machine': '',
                'coil_no': record.batch_no or '',
                'contract_no': record.contract_no or '',
                'customer': record.customer_alias or '',
                'output_tons': _tons_from_pair(record.net_weight_tons, record.net_weight_kg),
                'status': record.status_name or '',
                'source_table': 'mes_stock_records',
            }
        )

    energy_records = (
        db.query(MachineEnergyRecord, MobileShiftReport, Workshop, ShiftConfig, Equipment)
        .join(MobileShiftReport, MachineEnergyRecord.shift_report_id == MobileShiftReport.id)
        .join(Workshop, MobileShiftReport.workshop_id == Workshop.id)
        .join(ShiftConfig, MobileShiftReport.shift_config_id == ShiftConfig.id)
        .outerjoin(Equipment, MachineEnergyRecord.machine_id == Equipment.id)
        .filter(MobileShiftReport.business_date == business_date)
        .order_by(MachineEnergyRecord.id.asc())
        .all()
    )
    for energy, report, workshop, shift, equipment in energy_records:
        rows.append(
            {
                'business_date': report.business_date.isoformat(),
                'workshop': workshop.name,
                'shift': shift.name,
                'process': '能耗',
                'machine': energy.machine_name or (equipment.name if equipment else ''),
                'machine_code': energy.machine_code or (equipment.code if equipment else ''),
                'energy_kwh': _to_float(energy.energy_kwh),
                'gas_m3': _to_float(energy.gas_m3),
                'source_table': 'machine_energy_records',
            }
        )

    consumable_rows = (
        db.query(DailyConsumableLog, Workshop)
        .join(Workshop, DailyConsumableLog.workshop_id == Workshop.id)
        .filter(DailyConsumableLog.business_date == business_date)
        .order_by(DailyConsumableLog.id.asc())
        .all()
    )
    for log, workshop in consumable_rows:
        payload = log.payload or {}
        consumable_metrics = _consumable_payload_metrics(payload)
        rows.append(
            {
                'business_date': log.business_date.isoformat(),
                'workshop': workshop.name,
                'shift': '',
                'process': '内勤辅材',
                'machine': '',
                'output_tons': _to_float(payload.get('packaging_inbound_output_tons')),
                'energy_kwh': _to_float(payload.get('electricity_daily')),
                'gas_m3': _to_float(payload.get('gas_daily')),
                **consumable_metrics,
                'consumable_payload': consumable_metrics,
                'source_table': 'daily_consumable_logs',
            }
        )

    cost_rows = (
        db.query(CostDailyResult, Workshop)
        .outerjoin(Workshop, CostDailyResult.workshop_code == Workshop.code)
        .filter(CostDailyResult.business_date == business_date)
        .order_by(CostDailyResult.id.asc())
        .all()
    )
    for cost, workshop in cost_rows:
        rows.append(
            {
                'business_date': cost.business_date.isoformat(),
                'workshop': workshop.name if workshop else cost.workshop_code,
                'shift': '',
                'process': '成本策略',
                'machine': '',
                'strategy_code': cost.strategy_code,
                'cost_caliber': cost.caliber,
                'total_cost': _to_float(cost.total_cost),
                'cost_per_ton': _to_float(cost.output_ton_cost),
                'throughput_cost_per_ton': _to_float(cost.throughput_ton_cost),
                'breakdown_count': cost.breakdown_count,
                'process_count': cost.process_count,
                'source_table': 'cost_daily_result',
            }
        )
    return rows
