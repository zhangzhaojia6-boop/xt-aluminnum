from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import production_business_day_start_label, production_business_window
from app.models.master import Equipment, Workshop
from app.services import realtime_service
from app.services.report import daily_overview_builder
from app.services.report._utils import _to_float


def _round2(value: Any) -> float:
    return round(_to_float(value), 2)


def _source_label(payload: dict[str, Any]) -> str:
    return str(payload.get('source_label') or '无数据')


def _source_basis(payload: dict[str, Any]) -> str:
    return str(payload.get('source_basis') or 'none')


def _machine_row(workshop: Workshop, machine_id: int, bucket: dict[str, Any]) -> dict[str, Any]:
    input_weight = _round2(bucket.get('input'))
    output_weight = _round2(bucket.get('output'))
    return {
        'workshop_id': int(workshop.id),
        'workshop_code': workshop.code,
        'workshop_name': workshop.name,
        'machine_id': machine_id,
        'machine_name': bucket.get('machine_name') or 'MES未匹配机台',
        'machine_binding_status': bucket.get('machine_binding_status') or 'unbound',
        'input_weight': input_weight,
        'machine_input_weight': input_weight,
        'machine_down_machine_output': output_weight,
        'scrap_weight': _round2(bucket.get('scrap')),
        'row_count': int(bucket.get('row_count') or 0),
        'pass_count_total': int(bucket.get('pass_count_total') or 0),
        'source_basis': _source_basis(bucket),
        'source_label': _source_label(bucket),
        'binding_sources': dict(bucket.get('binding_sources') or {}),
    }


def _source_mapping() -> dict[str, Any]:
    return {
        'workshop_production': {
            'meaning': '车间产量',
            'rule': '最终产出口径；铸二/铸三/热轧优先按 MES 坯料明细重量，冷轧只统计已标记最终工序的重量',
            'projection_tables': ['mes_material_records', 'mes_workshop_process_records', 'work_order_entries'],
            'billet_source_page': '坯料管理 / 坯料明细',
            'billet_source_table': 'MES_Material',
            'billet_weight_field': 'Weight',
            'billet_status_filter': ['已使用', '未使用'],
        },
        'workshop_down_machine': {
            'meaning': '车间下机量',
            'source_page': '车间生产管理 / 车间报表',
            'source_table': 'MES_ProductProcessRecord',
            'source_workshop_field': 'WorkShop',
            'source_process_field': 'Process',
            'source_machine_field': 'DeviceName',
            'source_weight_field': 'EndWeight',
            'source_time_field': 'EndDatetime',
            'projection_table': 'mes_workshop_process_records',
            'projection_weight_field': 'output_weight_tons',
            'projection_date_field': 'business_date',
            'rule': '按车间汇总所有 MES 过站下机重量；坯料车间沿用 MES 坯料卷投影',
        },
        'workshop_feeding': {
            'meaning': '车间投料量',
            'source_page': '车间生产管理 / 车间报表',
            'source_table': 'MES_ProductProcessRecord',
            'source_workshop_field': 'WorkShop',
            'source_process_field': 'Process',
            'source_machine_field': 'DeviceName',
            'source_weight_field': 'BeginWeight',
            'source_time_field': 'EndDatetime',
            'projection_table': 'mes_workshop_process_records',
            'projection_weight_field': 'input_weight_tons',
            'projection_date_field': 'business_date',
            'rule': '按 MES 车间报表上机重量汇总，不从卷当前车间反推',
        },
        'machine_input': {
            'meaning': '机台上机量',
            'source_page': '车间生产管理 / 车间报表',
            'source_table': 'MES_ProductProcessRecord',
            'source_machine_field': 'DeviceName',
            'source_process_field': 'Process',
            'source_weight_field': 'BeginWeight',
            'source_time_field': 'EndDatetime',
            'projection_table': 'mes_workshop_process_records',
            'projection_machine_field': 'device_name',
            'projection_weight_field': 'input_weight_tons',
            'unmatched_rule': '本地未绑定的 MES 机台保留为 MES未匹配机台，不猜测归属',
        },
        'machine_down_machine': {
            'meaning': '机台下机量',
            'source_page': '车间生产管理 / 车间报表',
            'source_table': 'MES_ProductProcessRecord',
            'source_machine_field': 'DeviceName',
            'source_process_field': 'Process',
            'source_weight_field': 'EndWeight',
            'source_time_field': 'EndDatetime',
            'projection_table': 'mes_workshop_process_records',
            'projection_machine_field': 'device_name',
            'projection_weight_field': 'output_weight_tons',
            'unmatched_rule': '本地未绑定的 MES 机台保留为 MES未匹配机台，不猜测归属',
        },
    }


def build_mes_workshop_machine_reconciliation(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> dict[str, Any]:
    workshops_query = db.query(Workshop).filter(Workshop.is_active.is_(True))
    if workshop_id is not None:
        workshops_query = workshops_query.filter(Workshop.id == workshop_id)
    workshops = workshops_query.order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()

    machines_query = db.query(Equipment).filter(Equipment.is_active.is_(True))
    if workshop_id is not None:
        machines_query = machines_query.filter(Equipment.workshop_id == workshop_id)
    machines = machines_query.order_by(Equipment.sort_order.asc(), Equipment.id.asc()).all()

    production_scope = daily_overview_builder._mixed_workshop_output_scope_by_workshop(
        db,
        target_date,
        target_date,
    )
    machine_scope, authoritative_workshop_ids = realtime_service._load_mes_machine_output_scope(
        db,
        business_date=target_date,
        workshops=workshops,
        machines=machines,
    )

    machine_rows_by_workshop: dict[int, list[dict[str, Any]]] = {}
    for (bucket_workshop_id, machine_id), bucket in machine_scope.items():
        workshop = next((item for item in workshops if int(item.id) == int(bucket_workshop_id)), None)
        if workshop is None:
            continue
        machine_rows_by_workshop.setdefault(int(workshop.id), []).append(_machine_row(workshop, int(machine_id), bucket))

    workshop_rows: list[dict[str, Any]] = []
    for workshop in workshops:
        wid = int(workshop.id)
        production_payload = production_scope.get(wid, {})
        machine_rows = sorted(
            machine_rows_by_workshop.get(wid, []),
            key=lambda item: (item['machine_binding_status'] != 'bound', str(item['machine_name'] or '')),
        )
        machine_down_machine_output = _round2(sum(_to_float(item.get('machine_down_machine_output')) for item in machine_rows))
        machine_input_weight = _round2(sum(_to_float(item.get('machine_input_weight')) for item in machine_rows))
        row_count = int(sum(int(item.get('row_count') or 0) for item in machine_rows))
        pass_count_total = int(sum(int(item.get('pass_count_total') or 0) for item in machine_rows))
        down_machine_output = _round2(production_payload.get('process_output'))
        if down_machine_output == 0 and machine_down_machine_output > 0:
            down_machine_output = machine_down_machine_output
        input_weight = machine_input_weight
        if input_weight == 0:
            input_weight = _round2(production_payload.get('input'))

        workshop_rows.append(
            {
                'workshop_id': wid,
                'workshop_code': workshop.code,
                'workshop_name': workshop.name,
                'business_day_start': production_business_day_start_label(workshop.name),
                'production_output': _round2(production_payload.get('output')),
                'workshop_down_machine_output': down_machine_output,
                'machine_down_machine_output': machine_down_machine_output,
                'input_weight': input_weight,
                'workshop_feeding_input': input_weight,
                'machine_input_weight': machine_input_weight,
                'row_count': row_count,
                'pass_count_total': pass_count_total or int(production_payload.get('pass_count_total') or 0),
                'machine_count': len(machine_rows),
                'unbound_machine_count': len([item for item in machine_rows if item.get('machine_binding_status') == 'unbound']),
                'authoritative_mes_output': wid in authoritative_workshop_ids,
                'process_stage_outputs': dict(production_payload.get('process_stage_outputs') or {}),
                'production_source_basis': _source_basis(production_payload),
                'production_source_label': _source_label(production_payload),
                'down_machine_source_basis': _source_basis(production_payload),
                'down_machine_source_label': _source_label(production_payload),
                'workshop_feeding_source_basis': 'mes_workshop_process_records' if machine_input_weight > 0 else _source_basis(production_payload),
                'workshop_feeding_source_label': 'MES 车间报表' if machine_input_weight > 0 else _source_label(production_payload),
                'machines': machine_rows,
            }
        )

    window_start, window_end = production_business_window(target_date)
    workshop_time_policy = [
        {
            'workshop_id': int(workshop.id),
            'workshop_name': workshop.name,
            'business_day_start': production_business_day_start_label(workshop.name),
        }
        for workshop in workshops
    ]
    return {
        'target_date': target_date.isoformat(),
        'business_day': {
            'start': window_start.isoformat(),
            'end': window_end.isoformat(),
            'start_label': production_business_day_start_label(),
            'policy': {
                'default': '07:50-07:50',
                '铸二': '10:00-10:00',
                '铸三': '10:00-10:00',
                '热轧': '10:00-10:00',
            },
            'workshops': workshop_time_policy,
        },
        'source_mapping': _source_mapping(),
        'totals': {
            'production_output': _round2(sum(_to_float(item.get('production_output')) for item in workshop_rows)),
            'workshop_down_machine_output': _round2(sum(_to_float(item.get('workshop_down_machine_output')) for item in workshop_rows)),
            'machine_down_machine_output': _round2(sum(_to_float(item.get('machine_down_machine_output')) for item in workshop_rows)),
            'workshop_feeding_input': _round2(sum(_to_float(item.get('workshop_feeding_input')) for item in workshop_rows)),
            'machine_input_weight': _round2(sum(_to_float(item.get('machine_input_weight')) for item in workshop_rows)),
            'row_count': int(sum(int(item.get('row_count') or 0) for item in workshop_rows)),
            'unbound_machine_count': int(sum(int(item.get('unbound_machine_count') or 0) for item in workshop_rows)),
        },
        'workshops': workshop_rows,
    }
