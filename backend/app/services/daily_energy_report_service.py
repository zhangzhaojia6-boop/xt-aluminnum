from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Any

import pandas as pd


WORKSHOP_LABEL_MAP = {
    '铸锭': 'ZD',
    '铸二': 'ZR2',
    '铸三': 'ZR3',
    '2050': 'LZ2050',
    '1850': 'LZ1850',
    '1650': 'LZ1650',
    '1450': 'LZ1450',
    '花纹板': 'HWB',
    '热轧': 'RZ',
    '拉矫': 'JZ',
    '拉退火炉': 'JZ',
    '精整': 'JZ',
    '园区精整': 'JQ',
    '北线': 'ZXTF',
    '南线': 'ZXTF',
}

SKIP_LABELS = {
    '合计',
    '总表',
    '总表2',
    '差值',
    '差比',
    '百分比',
    '高压合计',
    '铸五制水房',
    '全油回收',
    '回收',
    '空压机',
    '水泵',
    '铝灰回收',
    '彩涂',
    '餐厅',
    '大修',
    '老厂',
    '生活区',
    '生产办公室',
    '园区北线',
    '园区南线',
}


@dataclass(slots=True)
class ParsedDailyEnergyRow:
    business_date: date
    source_kind: str
    source_file: str
    source_sheet: str
    source_row_no: int
    source_label: str
    workshop_code: str | None
    energy_type: str
    energy_value: float | None
    unit: str
    status: str
    error_msg: str | None = None

    @property
    def raw_data(self) -> dict[str, Any]:
        return {
            'source_kind': self.source_kind,
            'source_file': self.source_file,
            'source_sheet': self.source_sheet,
            'source_row_no': self.source_row_no,
            'source_label': self.source_label,
            'energy_value': self.energy_value,
            'unit': self.unit,
        }

    @property
    def mapped_data(self) -> dict[str, Any]:
        return {
            'business_date': self.business_date.isoformat(),
            'source_kind': self.source_kind,
            'source_file': self.source_file,
            'source_sheet': self.source_sheet,
            'source_row_no': self.source_row_no,
            'source_label': self.source_label,
            'workshop_code': self.workshop_code,
            'shift_code': None,
            'energy_type': self.energy_type,
            'energy_value': self.energy_value,
            'unit': self.unit,
            'status': self.status,
        }


def daily_energy_row_summary_fields() -> list[str]:
    return [
        'business_date',
        'source_kind',
        'source_label',
        'workshop_code',
        'shift_code',
        'energy_type',
        'energy_value',
        'unit',
        'status',
    ]


def _is_blank(value: object | None) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    return str(value).strip() == ''


def _normalize_label(value: object | None) -> str:
    if _is_blank(value):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return re.sub(r'\s+', '', text)


def _to_float(value: object | None) -> float | None:
    if _is_blank(value):
        return None
    if isinstance(value, str):
        value = value.replace(',', '').strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _day_number(value: object | None) -> int | None:
    if _is_blank(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        day = int(value)
        return day if 1 <= day <= 31 else None
    match = re.search(r'(\d{1,2})', str(value))
    if not match:
        return None
    day = int(match.group(1))
    return day if 1 <= day <= 31 else None


def _workshop_code_for(label: str) -> str | None:
    if label in WORKSHOP_LABEL_MAP:
        return WORKSHOP_LABEL_MAP[label]
    if label in SKIP_LABELS:
        return None
    return None


def _row_for_value(
    *,
    business_date: date,
    source_kind: str,
    source_file: str,
    source_sheet: str,
    source_row_no: int,
    source_label: str,
    mapping_label: str,
    energy_type: str,
    energy_value: float,
    unit: str,
) -> ParsedDailyEnergyRow:
    workshop_code = _workshop_code_for(mapping_label)
    if workshop_code:
        return ParsedDailyEnergyRow(
            business_date=business_date,
            source_kind=source_kind,
            source_file=source_file,
            source_sheet=source_sheet,
            source_row_no=source_row_no,
            source_label=source_label,
            workshop_code=workshop_code,
            energy_type=energy_type,
            energy_value=round(energy_value, 3),
            unit=unit,
            status='success',
        )
    return ParsedDailyEnergyRow(
        business_date=business_date,
        source_kind=source_kind,
        source_file=source_file,
        source_sheet=source_sheet,
        source_row_no=source_row_no,
        source_label=source_label,
        workshop_code=None,
        energy_type=energy_type,
        energy_value=round(energy_value, 3),
        unit=unit,
        status='skipped',
        error_msg=f'unmapped energy label: {source_label}',
    )


def _read_excel_sheets(workbook_path: Path) -> list[tuple[str, pd.DataFrame]]:
    xl = pd.ExcelFile(workbook_path)
    sheets: list[tuple[str, pd.DataFrame]] = []
    for sheet_name in xl.sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None)
        if not frame.empty:
            sheets.append((str(sheet_name), frame))
    return sheets


def _sheet_text(frame: pd.DataFrame, *, rows: int = 3) -> str:
    values: list[str] = []
    for row_index in range(min(len(frame), rows)):
        values.extend(str(value) for value in frame.iloc[row_index].tolist() if not _is_blank(value))
    return ' '.join(values)


def _find_electricity_header(frame: pd.DataFrame, report_date: date) -> tuple[int, int] | None:
    for row_index in range(min(len(frame), 8)):
        row = frame.iloc[row_index]
        if not any('车间/日期' in str(value) for value in row.tolist() if not _is_blank(value)):
            continue
        for col_index, value in enumerate(row.tolist()):
            if _day_number(value) == report_date.day:
                return row_index, col_index
    return None


def parse_workshop_electricity_workbook(
    workbook_path: str | Path,
    *,
    report_date: date,
) -> list[ParsedDailyEnergyRow]:
    path = Path(workbook_path)
    candidates: list[list[ParsedDailyEnergyRow]] = []
    for sheet_name, frame in _read_excel_sheets(path):
        header = _find_electricity_header(frame, report_date)
        if header is None:
            continue
        header_row, day_col = header
        rows: list[ParsedDailyEnergyRow] = []
        for row_index in range(header_row + 1, len(frame)):
            source_label = _normalize_label(frame.iat[row_index, 0] if frame.shape[1] else None)
            value = _to_float(frame.iat[row_index, day_col] if day_col < frame.shape[1] else None)
            if not source_label or value is None or value == 0:
                continue
            rows.append(
                _row_for_value(
                    business_date=report_date,
                    source_kind='workshop_electricity',
                    source_file=path.name,
                    source_sheet=sheet_name,
                    source_row_no=row_index + 1,
                    source_label=source_label,
                    mapping_label=source_label,
                    energy_type='electricity',
                    energy_value=value,
                    unit='kWh',
                )
            )
        candidates.append(rows)
    return max(candidates, key=len, default=[])


def _find_gas_day_row(frame: pd.DataFrame, report_date: date) -> int | None:
    for row_index in range(min(len(frame), 40)):
        if _day_number(frame.iat[row_index, 0] if frame.shape[1] else None) == report_date.day:
            return row_index
    return None


def _find_gas_header_rows(frame: pd.DataFrame, day_row: int) -> tuple[int, int] | None:
    for row_index in range(day_row - 1, -1, -1):
        row = frame.iloc[row_index]
        if any('车间/日期' in str(value) for value in row.tolist() if not _is_blank(value)):
            return row_index, row_index + 1
    return None


def parse_workshop_gas_workbook(
    workbook_path: str | Path,
    *,
    report_date: date,
) -> list[ParsedDailyEnergyRow]:
    path = Path(workbook_path)
    candidates: list[list[ParsedDailyEnergyRow]] = []
    for sheet_name, frame in _read_excel_sheets(path):
        if '抄表' in sheet_name or '抄表' in _sheet_text(frame):
            continue
        day_row = _find_gas_day_row(frame, report_date)
        if day_row is None:
            continue
        header_rows = _find_gas_header_rows(frame, day_row)
        if header_rows is None:
            continue
        header_row, subheader_row = header_rows
        rows: list[ParsedDailyEnergyRow] = []
        current_label = ''
        for col_index in range(1, frame.shape[1]):
            top_label = _normalize_label(frame.iat[header_row, col_index])
            if top_label:
                current_label = top_label
            mapping_label = current_label
            sub_label = _normalize_label(frame.iat[subheader_row, col_index])
            value = _to_float(frame.iat[day_row, col_index])
            if not mapping_label or value is None or value == 0:
                continue
            source_label = f'{mapping_label}/{sub_label}' if sub_label else mapping_label
            rows.append(
                _row_for_value(
                    business_date=report_date,
                    source_kind='workshop_gas',
                    source_file=path.name,
                    source_sheet=sheet_name,
                    source_row_no=day_row + 1,
                    source_label=source_label,
                    mapping_label=mapping_label,
                    energy_type='gas',
                    energy_value=value,
                    unit='m3',
                )
            )
        candidates.append(rows)
    return max(candidates, key=len, default=[])


def parse_daily_energy_workbooks(
    *,
    report_date: date,
    electricity_file: str | Path | None = None,
    gas_file: str | Path | None = None,
) -> list[ParsedDailyEnergyRow]:
    rows: list[ParsedDailyEnergyRow] = []
    if electricity_file:
        rows.extend(parse_workshop_electricity_workbook(electricity_file, report_date=report_date))
    if gas_file:
        rows.extend(parse_workshop_gas_workbook(gas_file, report_date=report_date))
    return rows
