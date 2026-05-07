from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
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


def _build_lineage_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


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
        'issues': issues,
        'quality_status': quality_status,
    }
    mapped_data = {
        **draft_payload,
        'lineage_hash': _build_lineage_hash(draft_payload),
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
    parsed_rows: list[ParsedDailyProductionSheet] = []
    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, engine=engine)
        if not is_daily_production_summary_sheet(str(sheet_name), frame):
            continue
        parsed_rows.append(
            parse_daily_production_sheet(
                str(sheet_name),
                frame,
                source_batch_id=source_batch_id,
                year_hint=year_hint,
                report_date_override=report_date_override,
            )
        )
    return parsed_rows
