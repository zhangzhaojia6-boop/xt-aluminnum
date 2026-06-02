from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.business_time import resolve_production_business_date
from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.services.contract_canonical_service import build_contract_projection
from app.services.contract_progress_projection_service import build_contract_progress_projection

router = APIRouter(tags=['contracts'])


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _target_date(date_from: date | None, date_to: date | None) -> date:
    return date_to or date_from or resolve_production_business_date()


def _status_for_frontend(status: str | None) -> str:
    value = str(status or '').strip().lower()
    if value == 'stalled':
        return 'overdue'
    if value in {'completed', 'done', 'closed', 'finished'}:
        return 'completed'
    return 'active' if value else 'active'


def build_contracts_summary(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    target_date = _target_date(date_from, date_to)
    projection = build_contract_projection(db, target_date=target_date)
    progress = build_contract_progress_projection(db, target_date=target_date)

    contracts: list[dict[str, Any]] = []
    for item in progress.get('contracts') or []:
        delivered = _to_float(item.get('today_advanced_weight'))
        remaining = _to_float(item.get('remaining_weight'))
        total = delivered + remaining
        frontend_status = _status_for_frontend(item.get('status'))
        if status and frontend_status != status:
            continue
        contracts.append(
            {
                'contract_no': item.get('contract_no') or '-',
                'customer_name': item.get('customer_name') or '-',
                'total_quantity': round(total, 2),
                'delivered_quantity': round(delivered, 2),
                'progress_pct': round((delivered / total * 100) if total else 0, 2),
                'deadline': target_date.isoformat(),
                'status': frontend_status,
            }
        )

    delivered_total = sum(_to_float(item.get('delivered_quantity')) for item in contracts)
    remaining_total = sum(_to_float(item.get('total_quantity')) - _to_float(item.get('delivered_quantity')) for item in contracts)
    progress_total = delivered_total + remaining_total
    labels = [item['contract_no'] for item in contracts[:20]]

    return {
        'kpi': {
            'active_count': int(progress.get('active_contract_count') or 0),
            'fulfillment_pct': round((delivered_total / progress_total * 100) if progress_total else 0, 2),
            'overdue_count': int(progress.get('stalled_contract_count') or 0),
            'mtd_delivery_tons': round(_to_float(projection.get('month_to_date_contract_weight')), 2),
        },
        'progress': {
            'labels': labels,
            'series': [
                {'name': '已推进', 'data': [item['delivered_quantity'] for item in contracts[:20]]},
                {
                    'name': '剩余',
                    'data': [
                        round(_to_float(item['total_quantity']) - _to_float(item['delivered_quantity']), 2)
                        for item in contracts[:20]
                    ],
                },
            ],
        },
        'contracts': contracts,
    }


@router.get('/summary', name='contracts-summary')
def contracts_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ = current_user
    return build_contracts_summary(db, date_from=date_from, date_to=date_to, status=status)


@router.get('/export', name='contracts-export')
def contracts_export(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    _ = current_user
    data = build_contracts_summary(db, date_from=date_from, date_to=date_to, status=status)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['合同号', '客户', '合同量(吨)', '已交付(吨)', '进度(%)', '交期', '状态'])
    for row in data['contracts']:
        writer.writerow(
            [
                row.get('contract_no') or '',
                row.get('customer_name') or '',
                row.get('total_quantity') or 0,
                row.get('delivered_quantity') or 0,
                row.get('progress_pct') or 0,
                row.get('deadline') or '',
                row.get('status') or '',
            ]
        )
    return Response(
        content=buffer.getvalue().encode('utf-8-sig'),
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename=contracts_summary.csv'},
    )
