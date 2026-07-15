from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet


def extract_verified_file_fact_updates(
    *,
    file_name: str,
    content: bytes,
    business_date: date,
    file_sha256: str,
) -> dict[str, dict[str, Any]]:
    if Path(file_name).suffix.lower() not in {'.xlsx', '.xlsm'}:
        return {}
    try:
        workbook = load_workbook(BytesIO(content), data_only=True, read_only=False)
    except Exception:  # noqa: BLE001
        return {}
    modified = workbook.properties.modified
    modified_date = modified.date() if isinstance(modified, datetime) else modified
    if not isinstance(modified_date, date) or modified_date != business_date:
        return {}

    for sheet in workbook.worksheets:
        source_ref = _company_daily_yield_source(sheet, business_date=business_date)
        if source_ref is None:
            continue
        value = _yield_percent(sheet[source_ref['value_cell']].value)
        if value is None:
            continue
        return {
            'daily_yield_rate': {
                'value': round(value, 2),
                'unit': '%',
                'confidence': 0.99,
                'reason': '钉钉成品率工作簿确定性单元格映射',
                'source_ref': {
                    'parser': 'company_daily_yield_v1',
                    'sheet_name': sheet.title,
                    'workbook_modified_date': modified_date.isoformat(),
                    **source_ref,
                    'file_sha256': file_sha256,
                },
            }
        }
    return {}


def _company_daily_yield_source(sheet: Worksheet, *, business_date: date) -> dict[str, str] | None:
    if not _sheet_period_matches(sheet, business_date=business_date):
        return None
    date_header = _find_header(sheet, '日期')
    total_header = _find_header(sheet, '总成品率')
    if date_header is None or total_header is None:
        return None

    total_min_col, total_max_col, total_max_row = _merged_bounds(sheet, total_header)
    daily_header = _find_text_in_range(
        sheet,
        text='日合计',
        min_row=total_max_row + 1,
        max_row=min(total_max_row + 4, sheet.max_row),
        min_col=total_min_col,
        max_col=total_max_col,
    )
    if daily_header is None:
        return None

    _, _, date_header_max_row = _merged_bounds(sheet, date_header)
    first_data_row = max(date_header_max_row, daily_header.row) + 1
    matching_rows = [
        row_number
        for row_number in range(first_data_row, sheet.max_row + 1)
        if _cell_matches_business_date(
            sheet.cell(row=row_number, column=date_header.column).value,
            business_date=business_date,
        )
    ]
    if len(matching_rows) != 1:
        return None
    row_number = matching_rows[0]
    date_cell = sheet.cell(row=row_number, column=date_header.column)
    value_cell = sheet.cell(row=row_number, column=daily_header.column)
    if _yield_percent(value_cell.value) is None:
        return None
    return {
        'date_cell': date_cell.coordinate,
        'value_cell': value_cell.coordinate,
        'header_cell': total_header.coordinate,
    }


def _sheet_period_matches(sheet: Worksheet, *, business_date: date) -> bool:
    header_text = ' '.join(
        str(sheet.cell(row=row, column=column).value or '').strip()
        for row in range(1, min(sheet.max_row, 5) + 1)
        for column in range(1, min(sheet.max_column, 20) + 1)
    )
    month_match = re.search(r'(?<!\d)(\d{1,2})\s*月份?', header_text)
    if month_match is None or int(month_match.group(1)) != business_date.month:
        return False
    year_match = re.search(r'(20\d{2})\s*年', header_text)
    return year_match is None or int(year_match.group(1)) == business_date.year


def _find_header(sheet: Worksheet, text: str) -> Cell | None:
    return _find_text_in_range(
        sheet,
        text=text,
        min_row=1,
        max_row=min(sheet.max_row, 10),
        min_col=1,
        max_col=sheet.max_column,
    )


def _find_text_in_range(
    sheet: Worksheet,
    *,
    text: str,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> Cell | None:
    matches: list[Cell] = []
    for row in range(min_row, max_row + 1):
        for column in range(min_col, max_col + 1):
            cell = sheet.cell(row=row, column=column)
            if text in str(cell.value or '').replace(' ', ''):
                matches.append(cell)
    return matches[0] if len(matches) == 1 else None


def _merged_bounds(sheet: Worksheet, cell: Cell) -> tuple[int, int, int]:
    for merged in sheet.merged_cells.ranges:
        if cell.coordinate in merged:
            return merged.min_col, merged.max_col, merged.max_row
    return cell.column, cell.column, cell.row


def _cell_matches_business_date(value: Any, *, business_date: date) -> bool:
    if isinstance(value, datetime):
        return value.date() == business_date
    if isinstance(value, date):
        return value == business_date
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return int(value) == business_date.day and float(value).is_integer()
    clean = str(value or '').strip()
    return clean in {str(business_date.day), business_date.isoformat()}


def _yield_percent(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        clean = str(value).strip().replace(',', '')
        if clean.endswith('%'):
            clean = clean[:-1].strip()
        try:
            number = float(clean)
        except ValueError:
            return None
    if 0 < number <= 1:
        number *= 100
    if not 0 < number <= 100:
        return None
    return number
