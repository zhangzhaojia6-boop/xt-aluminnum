from __future__ import annotations

import csv
from datetime import date, timedelta
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.business_time import resolve_production_business_date
from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.services.mobile_report.summary import summarize_mobile_inventory

router = APIRouter(tags=['inventory'])

MAX_SUMMARY_DAYS = 31


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date_span(date_from: date | None, date_to: date | None) -> list[date]:
    start = date_from or date_to or resolve_production_business_date()
    end = date_to or start
    if end < start:
        start, end = end, start
    days = (end - start).days + 1
    days = min(days, MAX_SUMMARY_DAYS)
    return [start + timedelta(days=offset) for offset in range(days)]


def build_inventory_summary(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
) -> dict[str, Any]:
    labels: list[str] = []
    inbound_series: list[float] = []
    outbound_series: list[float] = []
    transactions: list[dict[str, Any]] = []
    warehouse_map: dict[str, dict[str, Any]] = {}

    total_stock = 0.0
    total_inbound = 0.0
    total_outbound = 0.0

    for target_date in _date_span(date_from, date_to):
        rows = summarize_mobile_inventory(db, target_date=target_date, workshop_id=warehouse_id)
        day_inbound = sum(_to_float(row.get('storage_finished')) for row in rows)
        day_outbound = sum(_to_float(row.get('shipment_weight')) for row in rows)
        day_stock = sum(
            _to_float(row.get('actual_inventory_weight')) or _to_float(row.get('finished_inventory_weight'))
            for row in rows
        )

        labels.append(target_date.isoformat())
        inbound_series.append(round(day_inbound, 2))
        outbound_series.append(round(day_outbound, 2))
        total_stock = day_stock
        total_inbound += day_inbound
        total_outbound += day_outbound

        for row in rows:
            warehouse_name = row.get('workshop_name') or row.get('source_label') or '未分配仓库'
            warehouse_key = str(row.get('workshop_id') or warehouse_name)
            warehouse_map[warehouse_key] = {'id': row.get('workshop_id') or warehouse_key, 'name': warehouse_name}

            inbound = _to_float(row.get('storage_finished'))
            outbound = _to_float(row.get('shipment_weight'))
            operator = row.get('source_label') or row.get('team_name') or '-'
            material_name = row.get('team_name') or row.get('source_label') or '成品'
            row_key = f"{target_date.isoformat()}-{warehouse_key}-{row.get('team_id') or 'owner'}"
            if inbound:
                transactions.append(
                    {
                        'id': f'{row_key}-in',
                        'transaction_date': target_date.isoformat(),
                        'warehouse_name': warehouse_name,
                        'material_name': material_name,
                        'direction': 'inbound',
                        'quantity': round(inbound, 2),
                        'operator': operator,
                    }
                )
            if outbound:
                transactions.append(
                    {
                        'id': f'{row_key}-out',
                        'transaction_date': target_date.isoformat(),
                        'warehouse_name': warehouse_name,
                        'material_name': material_name,
                        'direction': 'outbound',
                        'quantity': round(outbound, 2),
                        'operator': operator,
                    }
                )

    return {
        'kpi': {
            'current_stock': round(total_stock, 2),
            'stock_change': round(total_inbound - total_outbound, 2),
            'inbound_today': round(total_inbound, 2),
            'outbound_today': round(total_outbound, 2),
            'anomaly_count': 0,
        },
        'trend': {
            'labels': labels,
            'series': [
                {'name': '入库', 'data': inbound_series},
                {'name': '出库', 'data': outbound_series},
            ],
        },
        'transactions': transactions,
        'warehouses': sorted(warehouse_map.values(), key=lambda item: str(item['name'])),
    }


@router.get('/summary', name='inventory-summary')
def inventory_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ = current_user
    return build_inventory_summary(db, date_from=date_from, date_to=date_to, warehouse_id=warehouse_id)


@router.get('/export', name='inventory-export')
def inventory_export(
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    _ = current_user
    data = build_inventory_summary(db, date_from=date_from, date_to=date_to, warehouse_id=warehouse_id)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['日期', '仓库', '物料', '方向', '数量(吨)', '操作人'])
    for row in data['transactions']:
        writer.writerow(
            [
                row.get('transaction_date') or '',
                row.get('warehouse_name') or '',
                row.get('material_name') or '',
                '入库' if row.get('direction') == 'inbound' else '出库',
                row.get('quantity') or 0,
                row.get('operator') or '',
            ]
        )
    return Response(
        content=buffer.getvalue().encode('utf-8-sig'),
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename=inventory_summary.csv'},
    )
