from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import hmac
import importlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


SUSPICIOUS_DAILY_OUTPUT_TONS = 5_000.0
HARD_BLOCK_DAILY_OUTPUT_TONS = 50_000.0
DAILY_PRODUCTION_FIELD_ORDER = [
    'business_date',
    'source_batch_id',
    'sheet_name',
    'source_unit',
    'row_count',
    'daily_input_tons',
    'month_to_date_input_tons',
    'daily_output_tons',
    'month_to_date_output_tons',
    'daily_scrap_tons',
    'month_to_date_scrap_tons',
    'lineage_hash',
    'quality_status',
    'issues',
]

_REPORT_OUTPUT_FIELDS = {
    '铸轧分厂': 'cast_roll',
    '铸锭': 'foundry',
    '热轧': 'hot_roll',
    '1650': 'cold_1650',
    '1850': 'cold_1850',
    '2050': 'cold_2050',
    '轧机': 'rolling',
    '在线退火': 'online_anneal',
    '拉矫': 'straightening',
    '精整': 'finishing',
    '剪切': 'shearing',
    '彩涂': 'coating',
}
_REPORT_PASS_PREFIXES = {'cold_1650', 'cold_1850', 'cold_2050', 'rolling'}
_REPORT_GAS_PREFIXES = {'cast_roll', 'foundry', 'hot_roll', 'coating'}


@dataclass(slots=True)
class ParsedDailyProductionSheet:
    sheet_name: str
    business_date: date | None
    mapped_data: dict[str, Any]
    raw_data: dict[str, Any]
    status: str
    error_msg: str | None


def daily_production_row_summary_fields() -> list[str]:
    return list(DAILY_PRODUCTION_FIELD_ORDER)


def _normalize_text(value: Any) -> str:
    text = str(value or '').strip()
    return text.replace('\n', '').replace('\r', '').replace(' ', '')


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if pd.isna(number) else number
    text = str(value or '').strip().replace(',', '')
    if not text or text in {'/', '-'}:
        return None
    match = re.search(r'-?\d+(?:\.\d+)?', text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _round_tons(value: float) -> float:
    return round(value, 3)


def build_daily_production_lineage_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def daily_production_lineage_is_valid(mapped_data: dict[str, Any]) -> bool:
    expected = str(mapped_data.get('lineage_hash') or '').strip().lower()
    if len(expected) != 64:
        return False
    payload = {key: value for key, value in mapped_data.items() if key != 'lineage_hash'}
    return hmac.compare_digest(expected, build_daily_production_lineage_hash(payload))


def _detect_business_date(sheet_name: str, frame: pd.DataFrame, *, year_hint: int | None) -> date | None:
    candidates = [_normalize_text(sheet_name)]
    for value in frame.head(4).fillna('').astype(str).values.flatten().tolist():
        text = _normalize_text(value)
        if text:
            candidates.append(text)

    year = year_hint or datetime.now(timezone.utc).year
    for text in candidates:
        numeric_match = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', text)
        if numeric_match:
            try:
                return date(int(numeric_match.group(1)), int(numeric_match.group(2)), int(numeric_match.group(3)))
            except ValueError:
                continue

        chinese_match = re.search(r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?', text)
        if chinese_match:
            parsed_year = int(chinese_match.group(1) or year)
            try:
                return date(parsed_year, int(chinese_match.group(2)), int(chinese_match.group(3)))
            except ValueError:
                continue
    return None


def is_daily_production_summary_sheet(sheet_name: str, frame: pd.DataFrame | None = None) -> bool:
    if '综合' in _normalize_text(sheet_name):
        return True
    if frame is None:
        return False
    title_text = ''.join(_normalize_text(value) for value in frame.head(2).fillna('').astype(str).values.flatten().tolist())
    return '综合日报表' in title_text or '生产系统综合日报表' in title_text


def _cell(row: list[Any], index: int) -> Any:
    return row[index] if index < len(row) else None


def _append_report_metric(
    metrics: list[dict[str, Any]],
    *,
    field_name: str,
    value: Any,
    unit: str,
    sheet_name: str,
    row_index: int,
    column_index: int,
) -> None:
    parsed = _parse_float(value)
    if parsed is None:
        return
    metrics.append(
        {
            'field_name': field_name,
            'value': round(parsed, 6),
            'unit': unit,
            'source_anchors': [
                {
                    'sheet_name': str(sheet_name),
                    'row_index': row_index,
                    'column_index': column_index,
                }
            ],
        }
    )


def _summary_report_metrics(sheet_name: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    rows = frame.fillna('').values.tolist()
    metric_header_row = next(
        (
            row_index
            for row_index, row in enumerate(rows)
            if _normalize_text(_cell(row, 1)) == '日产量'
            and _normalize_text(_cell(row, 2)) == '月累计产量'
        ),
        None,
    )
    if metric_header_row is not None:
        for row_index in range(metric_header_row + 1, len(rows)):
            row = rows[row_index]
            prefix = _REPORT_OUTPUT_FIELDS.get(_normalize_text(_cell(row, 0)))
            if prefix is None:
                continue
            _append_report_metric(
                metrics,
                field_name=f'{prefix}_daily',
                value=_cell(row, 1),
                unit='吨',
                sheet_name=sheet_name,
                row_index=row_index,
                column_index=1,
            )
            _append_report_metric(
                metrics,
                field_name=f'{prefix}_month',
                value=_cell(row, 2),
                unit='吨',
                sheet_name=sheet_name,
                row_index=row_index,
                column_index=2,
            )
            if prefix in _REPORT_PASS_PREFIXES:
                _append_report_metric(
                    metrics,
                    field_name=f'{prefix}_pass_daily',
                    value=_cell(row, 3),
                    unit='道',
                    sheet_name=sheet_name,
                    row_index=row_index,
                    column_index=3,
                )
                _append_report_metric(
                    metrics,
                    field_name=f'{prefix}_pass_month',
                    value=_cell(row, 4),
                    unit='道',
                    sheet_name=sheet_name,
                    row_index=row_index,
                    column_index=4,
                )
            _append_report_metric(
                metrics,
                field_name=f'{prefix}_electricity_per_ton_daily',
                value=_cell(row, 10),
                unit='kWh/吨',
                sheet_name=sheet_name,
                row_index=row_index,
                column_index=10,
            )
            _append_report_metric(
                metrics,
                field_name=f'{prefix}_electricity_per_ton_month',
                value=_cell(row, 11),
                unit='kWh/吨',
                sheet_name=sheet_name,
                row_index=row_index,
                column_index=11,
            )
            if prefix in _REPORT_GAS_PREFIXES:
                _append_report_metric(
                    metrics,
                    field_name=f'{prefix}_gas_per_ton_daily',
                    value=_cell(row, 15),
                    unit='m³/吨',
                    sheet_name=sheet_name,
                    row_index=row_index,
                    column_index=15,
                )
                _append_report_metric(
                    metrics,
                    field_name=f'{prefix}_gas_per_ton_month',
                    value=_cell(row, 16),
                    unit='m³/吨',
                    sheet_name=sheet_name,
                    row_index=row_index,
                    column_index=16,
                )

    total_columns: tuple[int, int] | None = None
    for row_index in range(min(6, len(rows))):
        row = rows[row_index]
        for column_index in range(20, len(row)):
            if _normalize_text(_cell(row, column_index)) != '产量':
                continue
            subheader = rows[row_index + 1] if row_index + 1 < len(rows) else []
            if _normalize_text(_cell(subheader, column_index)) == '日合计':
                total_columns = (column_index, column_index + 1)
                break
        if total_columns is not None:
            break
    if total_columns is not None:
        search_end = metric_header_row if metric_header_row is not None else len(rows)
        total_row_index = next(
            (
                row_index
                for row_index in range(search_end)
                if _normalize_text(_cell(rows[row_index], 0)) == '合计'
            ),
            None,
        )
        if total_row_index is not None:
            daily_column, month_column = total_columns
            _append_report_metric(
                metrics,
                field_name='total_output_daily',
                value=_cell(rows[total_row_index], daily_column),
                unit='吨',
                sheet_name=sheet_name,
                row_index=total_row_index,
                column_index=daily_column,
            )
            _append_report_metric(
                metrics,
                field_name='cost_basis_weight',
                value=_cell(rows[total_row_index], daily_column),
                unit='吨',
                sheet_name=sheet_name,
                row_index=total_row_index,
                column_index=daily_column,
            )
            _append_report_metric(
                metrics,
                field_name='total_output_month',
                value=_cell(rows[total_row_index], month_column),
                unit='吨',
                sheet_name=sheet_name,
                row_index=total_row_index,
                column_index=month_column,
            )
    return metrics


def _as_business_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if _normalize_text(value) == '':
        return None
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _outsourced_report_metrics(
    sheet_name: str,
    frame: pd.DataFrame,
    *,
    report_date: date,
) -> list[dict[str, Any]]:
    rows = frame.fillna('').values.tolist()
    header_row_index: int | None = None
    report_column: int | None = None
    month_columns: list[int] = []
    for row_index, row in enumerate(rows[:8]):
        dated_columns = [
            column_index
            for column_index, value in enumerate(row)
            if (parsed_date := _as_business_date(value)) is not None
            and parsed_date.year == report_date.year
            and parsed_date.month == report_date.month
            and parsed_date <= report_date
        ]
        current_column = next(
            (
                column_index
                for column_index in dated_columns
                if _as_business_date(_cell(row, column_index)) == report_date
            ),
            None,
        )
        if current_column is not None:
            header_row_index = row_index
            report_column = current_column
            month_columns = dated_columns
            break
    if header_row_index is None or report_column is None:
        return []

    daily_total = 0.0
    month_total = 0.0
    daily_seen = False
    month_seen = False
    daily_anchors: list[dict[str, Any]] = []
    month_anchors: list[dict[str, Any]] = []
    for row_index in range(header_row_index + 1, len(rows)):
        row = rows[row_index]
        label = _normalize_text(_cell(row, 0))
        if label.startswith('合计'):
            break
        if not label:
            continue
        daily_value = _parse_float(_cell(row, report_column))
        if daily_value is not None:
            daily_total += daily_value
            daily_seen = True
            daily_anchors.append(
                {'sheet_name': sheet_name, 'row_index': row_index, 'column_index': report_column}
            )
        for column_index in month_columns:
            value = _parse_float(_cell(row, column_index))
            if value is None:
                continue
            month_total += value
            month_seen = True
            month_anchors.append(
                {'sheet_name': sheet_name, 'row_index': row_index, 'column_index': column_index}
            )

    metrics: list[dict[str, Any]] = []
    if daily_seen:
        metrics.append(
            {
                'field_name': 'outsourced_daily',
                'value': round(daily_total, 6),
                'unit': '吨',
                'source_anchors': daily_anchors,
            }
        )
    if month_seen:
        metrics.append(
            {
                'field_name': 'outsourced_month',
                'value': round(month_total, 6),
                'unit': '吨',
                'source_anchors': month_anchors,
            }
        )
    return metrics


def _merge_report_metrics(parsed: ParsedDailyProductionSheet, metrics: list[dict[str, Any]]) -> None:
    if not metrics:
        return
    payload = {key: value for key, value in parsed.mapped_data.items() if key != 'lineage_hash'}
    existing = {
        str(item.get('field_name')): item
        for item in payload.get('report_metrics') or []
        if isinstance(item, dict) and item.get('field_name')
    }
    for metric in metrics:
        existing[str(metric['field_name'])] = metric
    payload['report_metrics'] = list(existing.values())
    parsed.mapped_data = {
        **payload,
        'lineage_hash': build_daily_production_lineage_hash(payload),
    }


def _has_production_values(row_payload: dict[str, Any]) -> bool:
    metric_values = [
        row_payload.get('daily_input_tons'),
        row_payload.get('month_to_date_input_tons'),
        row_payload.get('daily_output_tons'),
        row_payload.get('month_to_date_output_tons'),
        row_payload.get('daily_scrap_tons'),
        row_payload.get('month_to_date_scrap_tons'),
    ]
    meaningful = [value for value in metric_values if value not in (None, 0, 0.0)]
    return bool(meaningful)


def _is_production_section_stop(raw_row: list[Any]) -> bool:
    first_label = _normalize_text(_cell(raw_row, 0))
    row_text = ''.join(_normalize_text(value) for value in raw_row)
    if first_label in {'合计', '工业园', '车间转园区', '成品库转园区', '累计'}:
        return True
    return '日吨电耗' in row_text or '月累计产量' in row_text


def _extract_rows(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    current_workshop = ''

    for row_index, raw_row in enumerate(frame.fillna('').values.tolist()):
        if row_index < 3:
            continue
        if _is_production_section_stop(raw_row):
            break
        workshop_label = _normalize_text(_cell(raw_row, 0))
        project_label = _normalize_text(_cell(raw_row, 1))
        if workshop_label:
            current_workshop = workshop_label
        if not current_workshop and not project_label:
            continue

        row_payload = {
            'row_index': row_index,
            'workshop_label': current_workshop or None,
            'project_label': project_label or None,
            'daily_input_tons': _parse_float(_cell(raw_row, 2)),
            'month_to_date_input_tons': _parse_float(_cell(raw_row, 3)),
            'daily_output_tons': _parse_float(_cell(raw_row, 4)),
            'month_to_date_output_tons': _parse_float(_cell(raw_row, 5)),
            'daily_scrap_tons': _parse_float(_cell(raw_row, 7)),
            'month_to_date_scrap_tons': _parse_float(_cell(raw_row, 8)),
            'yield_rate': _parse_float(_cell(raw_row, 9)),
            'target_yield_rate': _parse_float(_cell(raw_row, 10)),
        }
        if not _has_production_values(row_payload):
            continue
        daily_output = row_payload.get('daily_output_tons')
        if daily_output is not None and daily_output > HARD_BLOCK_DAILY_OUTPUT_TONS:
            issues.append(
                {
                    'code': 'hard_block_kg_as_tons',
                    'message': f'每日产量日报值 {daily_output} 超过 {HARD_BLOCK_DAILY_OUTPUT_TONS}t，疑似把 kg 当作 t，已硬阻断。',
                    'row_index': row_index,
                    'workshop_label': row_payload['workshop_label'],
                    'project_label': row_payload['project_label'],
                    'value': daily_output,
                }
            )
        elif daily_output is not None and daily_output > SUSPICIOUS_DAILY_OUTPUT_TONS:
            issues.append(
                {
                    'code': 'suspicious_daily_output_tons',
                    'message': f'每日产量日报值超过 {SUSPICIOUS_DAILY_OUTPUT_TONS}t，请核对是否把 kg 当作 t。',
                    'row_index': row_index,
                    'workshop_label': row_payload['workshop_label'],
                    'project_label': row_payload['project_label'],
                    'value': daily_output,
                }
            )
        rows.append(row_payload)

    return rows, issues


def _sum_rows(rows: list[dict[str, Any]], field_name: str) -> float:
    return _round_tons(sum(float(row.get(field_name) or 0.0) for row in rows))


def parse_daily_production_sheet(
    sheet_name: str,
    frame: pd.DataFrame,
    *,
    source_batch_id: int | None = None,
    year_hint: int | None = None,
    report_date_override: date | None = None,
) -> ParsedDailyProductionSheet:
    detected_business_date = _detect_business_date(sheet_name, frame, year_hint=year_hint)
    business_date = report_date_override or detected_business_date
    rows, issues = _extract_rows(frame)
    if report_date_override is not None and detected_business_date is not None and detected_business_date != report_date_override:
        issues.append(
            {
                'code': 'stale_workbook_report_date',
                'message': f'每日产量表头日期 {detected_business_date.isoformat()} 与锁定报告日 {report_date_override.isoformat()} 不一致，已按锁定报告日解析。',
                'detected_business_date': detected_business_date.isoformat(),
                'locked_business_date': report_date_override.isoformat(),
            }
        )
    quality_status = 'ready'
    if issues:
        quality_status = 'warning'
    if any(item.get('code') == 'hard_block_kg_as_tons' for item in issues):
        quality_status = 'blocked'
    if not rows or business_date is None:
        quality_status = 'blocked'

    draft_payload = {
        'business_date': business_date.isoformat() if business_date else None,
        'source_batch_id': source_batch_id,
        'sheet_name': str(sheet_name),
        'source_unit': 't',
        'row_count': len(rows),
        'daily_input_tons': _sum_rows(rows, 'daily_input_tons'),
        'month_to_date_input_tons': _sum_rows(rows, 'month_to_date_input_tons'),
        'daily_output_tons': _sum_rows(rows, 'daily_output_tons'),
        'month_to_date_output_tons': _sum_rows(rows, 'month_to_date_output_tons'),
        'daily_scrap_tons': _sum_rows(rows, 'daily_scrap_tons'),
        'month_to_date_scrap_tons': _sum_rows(rows, 'month_to_date_scrap_tons'),
        'workshop_rows': rows,
        'report_metrics': _summary_report_metrics(str(sheet_name), frame),
        'issues': issues,
        'quality_status': quality_status,
    }
    mapped_data = {
        **draft_payload,
        'lineage_hash': build_daily_production_lineage_hash(draft_payload),
    }
    raw_data = {
        'sheet_name': str(sheet_name),
        'preview_rows': frame.head(8).fillna('').astype(str).values.tolist(),
    }
    status = 'success' if quality_status != 'blocked' else 'failed'
    error_msg = None if status == 'success' else '每日产量表未识别出日期或有效生产行，请检查表头和综合报表格式。'
    return ParsedDailyProductionSheet(
        sheet_name=str(sheet_name),
        business_date=business_date,
        mapped_data=mapped_data,
        raw_data=raw_data,
        status=status,
        error_msg=error_msg,
    )


def parse_daily_production_workbook(
    path: str | Path,
    *,
    source_batch_id: int | None = None,
    year_hint: int | None = None,
    report_date_override: date | None = None,
) -> list[ParsedDailyProductionSheet]:
    workbook_path = Path(path)
    if workbook_path.suffix.lower() == '.xlsx':
        engine = 'openpyxl'
    elif workbook_path.suffix.lower() == '.xls':
        importlib.import_module('xlrd')
        engine = 'xlrd'
    else:
        raise ValueError('Only xlsx/xls daily production workbooks are supported')
    excel = pd.ExcelFile(workbook_path, engine=engine)
    outsourced_sheets: list[tuple[str, pd.DataFrame]] = []
    summary_candidates: list[tuple[str, pd.DataFrame]] = []
    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, engine=engine)
        if '外加工' in _normalize_text(sheet_name):
            outsourced_sheets.append((str(sheet_name), frame))
        if not is_daily_production_summary_sheet(str(sheet_name), frame):
            continue
        summary_candidates.append((str(sheet_name), frame))

    parsed_rows: list[ParsedDailyProductionSheet] = []
    if summary_candidates:
        def summary_priority(candidate: tuple[str, pd.DataFrame]) -> int:
            normalized_name = _normalize_text(candidate[0])
            sheet_date = _detect_business_date(candidate[0], pd.DataFrame(), year_hint=year_hint)
            if sheet_date is not None and (
                report_date_override is None or sheet_date == report_date_override
            ):
                return 3
            if normalized_name == '综合报表':
                return 2
            return 1 if '综合' in normalized_name else 0

        selected_name, selected_frame = max(summary_candidates, key=summary_priority)
        parsed = parse_daily_production_sheet(
            selected_name,
            selected_frame,
            source_batch_id=source_batch_id,
            year_hint=year_hint,
            report_date_override=report_date_override,
        )
        ignored_sheets = [name for name, _frame in summary_candidates if name != selected_name]
        if ignored_sheets:
            payload = {key: value for key, value in parsed.mapped_data.items() if key != 'lineage_hash'}
            payload['issues'] = [
                *(payload.get('issues') or []),
                {
                    'code': 'ignored_duplicate_summary_sheet',
                    'selected_sheet': selected_name,
                    'ignored_sheets': ignored_sheets,
                },
            ]
            if payload.get('quality_status') == 'ready':
                payload['quality_status'] = 'warning'
            parsed.mapped_data = {
                **payload,
                'lineage_hash': build_daily_production_lineage_hash(payload),
            }
        parsed_rows.append(parsed)
    if parsed_rows and outsourced_sheets:
        selected_report_date = _as_business_date(parsed_rows[0].mapped_data.get('business_date'))
        if selected_report_date is not None:
            outsourced_metrics = [
                metric
                for sheet_name, frame in outsourced_sheets
                for metric in _outsourced_report_metrics(
                    sheet_name,
                    frame,
                    report_date=selected_report_date,
                )
            ]
            _merge_report_metrics(parsed_rows[0], outsourced_metrics)
    return parsed_rows
