from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


DETAIL_HEADERS = [
    '序号',
    '车间',
    '班次',
    '缺报人员',
    '登录账号',
    '缺报时间',
    '对应卷号',
    '问题类型',
    '缺失项',
    'MES命中数',
    'MES推断机列',
    '候选机列',
    '投入吨',
    '产出吨',
    '废料吨',
    '记录状态',
    '记录类型',
    '工单ID',
    '填报ID',
]

SUMMARY_HEADERS = [
    '车间',
    '缺报条数',
    '缺机列',
    '缺班次',
    'MES命中卷数',
    '未命中MES',
    '缺报人员',
    '候选机列',
    '投入吨',
    '产出吨',
    '废料吨',
]

MES_GAP_HEADERS = [
    '序号',
    '状态',
    '车间',
    '工序',
    '批号',
    '随行卡',
    '本地填报ID',
    'MES产出kg',
    '本地产出kg',
    'MES机列',
    '本地机列',
]

FIELD_LABELS = {
    'machine_id': '机列未填',
    'shift_id': '班次未填',
}

MES_GAP_STATUS_LABELS = {
    'missing_local_entry': 'MES有工序本地未填',
    'mes_batch_unmapped': '批号未映射',
    'local_entry_unassigned': '本地未归机列',
    'weight_mismatch': '重量不一致',
    'matched': '已匹配',
}


def _text(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _number(value: Any) -> float:
    try:
        return round(float(value or 0), 3)
    except (TypeError, ValueError):
        return 0.0


def _time_text(value: Any) -> str:
    text = _text(value, '')
    if not text:
        return '-'
    return text.replace('T', ' ')[:19]


def _missing_fields_text(item: dict[str, Any]) -> str:
    labels = [FIELD_LABELS.get(str(field), str(field)) for field in item.get('missing_fields') or []]
    return '、'.join(labels) or '-'


def _person_text(item: dict[str, Any]) -> str:
    return _text(item.get('created_by_user_name') or item.get('created_by_username'))


def _candidate_text(item: dict[str, Any]) -> str:
    names = item.get('machine_candidate_names') or []
    return '、'.join(str(name) for name in names if str(name).strip()) or '-'


def _issue_type(item: dict[str, Any]) -> str:
    missing_fields = set(item.get('missing_fields') or [])
    if 'machine_id' in missing_fields and int(item.get('mes_match_count') or 0) > 0:
        return 'MES抓到但机列未填'
    if 'machine_id' in missing_fields:
        return '机列未填'
    if 'shift_id' in missing_fields:
        return '班次未填'
    return '待补齐'


def _sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            _text(item.get('workshop_name')),
            _text(item.get('shift_name')),
            _person_text(item),
            _time_text(item.get('created_at')),
            _text(item.get('tracking_card_no')),
        ),
    )


def _append_title(ws, title: str, column_count: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=column_count)
    cell = ws.cell(row=1, column=1, value=title)
    cell.font = Font(bold=True, size=14, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor='17324D')
    cell.alignment = Alignment(horizontal='center')


def _style_table(ws, header_row: int, column_count: int) -> None:
    fill = PatternFill('solid', fgColor='D9EAF7')
    for col in range(1, column_count + 1):
        cell = ws.cell(row=header_row, column=col)
        cell.font = Font(bold=True, color='17324D')
        cell.fill = fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate
    ws.auto_filter.ref = f'A{header_row}:{get_column_letter(column_count)}{max(ws.max_row, header_row)}'


def _fit_columns(ws, max_width: int = 42) -> None:
    for column_cells in ws.columns:
        width = 10
        for cell in column_cells:
            width = max(width, min(len(str(cell.value or '')) + 2, max_width))
        ws.column_dimensions[get_column_letter(column_cells[0].column)].width = width


def _build_detail_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    rows = []
    for index, item in enumerate(_sort_items(items), start=1):
        rows.append(
            [
                index,
                _text(item.get('workshop_name')),
                _text(item.get('shift_name')),
                _person_text(item),
                _text(item.get('created_by_username')),
                _time_text(item.get('created_at')),
                _text(item.get('tracking_card_no')),
                _issue_type(item),
                _missing_fields_text(item),
                int(item.get('mes_match_count') or 0),
                _text(item.get('mes_machine_name')),
                _candidate_text(item),
                _number(item.get('input_weight')),
                _number(item.get('output_weight')),
                _number(item.get('scrap_weight')),
                _text(item.get('entry_status')),
                _text(item.get('entry_type')),
                item.get('work_order_id') or '',
                item.get('entry_id') or '',
            ]
        )
    return rows


def _build_summary_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'count': 0,
        'missing_machine': 0,
        'missing_shift': 0,
        'mes_hit': 0,
        'mes_miss': 0,
        'people': set(),
        'candidates': set(),
        'input': 0.0,
        'output': 0.0,
        'scrap': 0.0,
    })
    for item in items:
        workshop = _text(item.get('workshop_name'), '未标记车间')
        bucket = buckets[workshop]
        missing_fields = set(item.get('missing_fields') or [])
        bucket['count'] += 1
        bucket['missing_machine'] += 1 if 'machine_id' in missing_fields else 0
        bucket['missing_shift'] += 1 if 'shift_id' in missing_fields else 0
        if int(item.get('mes_match_count') or 0) > 0:
            bucket['mes_hit'] += 1
        else:
            bucket['mes_miss'] += 1
        person = _person_text(item)
        if person != '-':
            bucket['people'].add(person)
        for name in item.get('machine_candidate_names') or []:
            if str(name).strip():
                bucket['candidates'].add(str(name).strip())
        bucket['input'] += _number(item.get('input_weight'))
        bucket['output'] += _number(item.get('output_weight'))
        bucket['scrap'] += _number(item.get('scrap_weight'))

    rows = []
    for workshop, bucket in sorted(buckets.items(), key=lambda pair: (-pair[1]['count'], pair[0])):
        rows.append(
            [
                workshop,
                bucket['count'],
                bucket['missing_machine'],
                bucket['missing_shift'],
                bucket['mes_hit'],
                bucket['mes_miss'],
                '、'.join(sorted(bucket['people'])) or '-',
                '、'.join(sorted(bucket['candidates'])) or '-',
                round(bucket['input'], 3),
                round(bucket['output'], 3),
                round(bucket['scrap'], 3),
            ]
        )
    return rows


def _build_mes_gap_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    rows = []
    for index, item in enumerate(items, start=1):
        status = _text(item.get('status'), '')
        rows.append(
            [
                index,
                MES_GAP_STATUS_LABELS.get(status, status or '-'),
                _text(item.get('workshop_name')),
                _text(item.get('process_name')),
                _text(item.get('batch_no')),
                _text(item.get('tracking_card_no')),
                item.get('local_entry_id') or '',
                _number(item.get('mes_output_weight')),
                _number(item.get('local_output_weight')),
                _text(item.get('mes_machine_name')),
                _text(item.get('local_machine_name')),
            ]
        )
    return rows


def _append_mes_gap_sheet(workbook: Workbook, *, business_date: str, mes_fill_gaps: dict[str, Any]) -> None:
    mes_sheet = workbook.create_sheet('MES异常明细')
    _append_title(mes_sheet, f'MES异常明细 {business_date}', len(MES_GAP_HEADERS))
    mes_sheet.append([])
    mes_sheet.append(MES_GAP_HEADERS)
    rows = _build_mes_gap_rows(list(mes_fill_gaps.get('items') or []))
    if rows:
        for row in rows:
            mes_sheet.append(row)
    else:
        mes_sheet.append(['暂无MES异常'] + [''] * (len(MES_GAP_HEADERS) - 1))
    _style_table(mes_sheet, 3, len(MES_GAP_HEADERS))
    _fit_columns(mes_sheet)


def build_missing_report_workbook(payload: dict[str, Any]) -> bytes:
    business_date = _text(payload.get('business_date'), '')
    items = list(payload.get('items') or [])
    summary = dict(payload.get('summary') or {})

    workbook = Workbook()
    detail = workbook.active
    detail.title = '缺报明细'
    _append_title(detail, f'缺报明细 {business_date}', len(DETAIL_HEADERS))
    detail.cell(row=2, column=1, value=(
        f"共{int(summary.get('entry_count') or len(items))}条；"
        f"缺机列{int(summary.get('missing_machine_count') or 0)}条；"
        f"缺班次{int(summary.get('missing_shift_count') or 0)}条"
    ))
    detail.append([])
    detail.append(DETAIL_HEADERS)
    detail_rows = _build_detail_rows(items)
    if detail_rows:
        for row in detail_rows:
            detail.append(row)
    else:
        detail.append(['暂无缺报'] + [''] * (len(DETAIL_HEADERS) - 1))
    _style_table(detail, 4, len(DETAIL_HEADERS))
    _fit_columns(detail)

    summary_sheet = workbook.create_sheet('车间汇总')
    _append_title(summary_sheet, f'车间缺报汇总 {business_date}', len(SUMMARY_HEADERS))
    summary_sheet.append([])
    summary_sheet.append(SUMMARY_HEADERS)
    summary_rows = _build_summary_rows(items)
    if summary_rows:
        for row in summary_rows:
            summary_sheet.append(row)
    else:
        summary_sheet.append(['暂无缺报'] + [''] * (len(SUMMARY_HEADERS) - 1))
    _style_table(summary_sheet, 3, len(SUMMARY_HEADERS))
    _fit_columns(summary_sheet)

    mes_fill_gaps = payload.get('mes_fill_gaps')
    if isinstance(mes_fill_gaps, dict):
        _append_mes_gap_sheet(workbook, business_date=business_date, mes_fill_gaps=mes_fill_gaps)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
