"""采购管理后台：台账、导出、供应商、作废、统计。走单规则在 procurement_service。"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import local_now
from app.domain import procurement_flow as flow
from app.models.master import Workshop
from app.models.procurement import ProcurementQuote, ProcurementRequest, ProcurementStepLog, ProcurementSupplier
from app.models.system import User
from app.services import procurement_service as service
from app.services.audit_service import log_action

MAX_PAGE_SIZE = 100
# 撤销和库存够用的单子没有花钱，不算进金额
NOT_PURCHASED = {flow.STATUS_CANCELLED, flow.STATUS_CLOSED_STOCK}
SUPPLIER_STATUSES = {flow.SUPPLIER_PENDING, flow.SUPPLIER_QUALIFIED, flow.SUPPLIER_BLACKLISTED}
CSV_COLUMNS = (
    ('request_no', '单号'), ('created_on', '提报日期'), ('workshop_name', '车间'), ('requester_name', '提报人'),
    ('material_name', '物料'), ('specification', '规格'), ('category', '类别'), ('quantity', '数量'), ('unit', '单位'),
    ('amount', '金额'), ('supplier', '供应商'), ('step_label', '环节'), ('status_label', '状态'),
    ('emergency_label', '紧急'), ('overdue_label', '超时'), ('backfill_due_on', '补手续期限'),
)
STATUS_LABELS = {
    flow.STATUS_OPEN: '在办', flow.STATUS_ARCHIVED: '已归档',
    flow.STATUS_CLOSED_STOCK: '库存充足', flow.STATUS_CANCELLED: '已撤销',
}


def _require_view_all(db: Session, user: User) -> set[str]:
    roles = service.user_roles(db, user)
    if not service.can_view_all(user, roles):
        raise service.ProcurementError(403, '没有查看全部台账的权限')
    return roles


def _filtered_rows(db: Session, filters: dict[str, Any]) -> list[ProcurementRequest]:
    query = db.query(ProcurementRequest)
    if filters.get('status'):
        query = query.filter(ProcurementRequest.status == filters['status'])
    if filters.get('step'):
        query = query.filter(ProcurementRequest.current_step == filters['step'])
    if filters.get('category'):
        query = query.filter(ProcurementRequest.category == filters['category'])
    if filters.get('emergency') is not None:
        query = query.filter(ProcurementRequest.is_emergency.is_(bool(filters['emergency'])))
    if filters.get('workshop_id'):
        query = query.filter(ProcurementRequest.workshop_id == filters['workshop_id'])
    if filters.get('supplier'):
        query = query.filter(ProcurementRequest.supplier.ilike(f"%{filters['supplier'].strip()}%"))
    if filters.get('keyword'):
        like = f"%{filters['keyword'].strip()}%"
        query = query.filter(ProcurementRequest.material_name.ilike(like) | ProcurementRequest.request_no.ilike(like))
    rows = query.order_by(ProcurementRequest.id.desc()).all()
    date_from, date_to = filters.get('date_from'), filters.get('date_to')
    if date_from or date_to:
        rows = [row for row in rows if _in_range(row, date_from, date_to)]
    return rows


def _in_range(row: ProcurementRequest, date_from: date | None, date_to: date | None) -> bool:
    created = service._aware(row.created_at).astimezone(local_now().tzinfo).date()
    return (date_from is None or created >= date_from) and (date_to is None or created <= date_to)


def _ledger_items(db: Session, *, user: User, roles: set[str], filters: dict[str, Any], now: datetime | None) -> list[dict]:
    rows = _filtered_rows(db, filters)
    users = dict(db.query(User.id, User.name).filter(User.id.in_({row.requester_id for row in rows})).all()) if rows else {}
    workshops = dict(db.query(Workshop.id, Workshop.name).all())
    items = []
    for row in rows:
        item = service.serialize_request(db, row, user=user, roles=roles, now=now)
        item['requester_name'] = users.get(row.requester_id)
        item['workshop_name'] = workshops.get(row.workshop_id)
        items.append(item)
    if filters.get('overdue') is not None:
        items = [item for item in items if item['is_overdue'] is bool(filters['overdue'])]
    return items


def ledger(db: Session, *, user: User, filters: dict[str, Any], page: int = 1, page_size: int = 20, now: datetime | None = None) -> dict:
    roles = _require_view_all(db, user)
    items = _ledger_items(db, user=user, roles=roles, filters=filters, now=now)
    page = max(1, int(page))
    page_size = min(MAX_PAGE_SIZE, max(1, int(page_size)))
    start = (page - 1) * page_size
    return {
        'items': items[start:start + page_size],
        'total': len(items),
        'page': page,
        'page_size': page_size,
        'total_amount': str(sum((Decimal(item['amount']) for item in items if item['status'] not in NOT_PURCHASED), Decimal('0'))),
    }


def _csv_cell(value: Any) -> str:
    """防止表格软件把自由文本当公式执行。"""
    text = '' if value is None else str(value)
    return f"'{text}" if text[:1] in {'=', '+', '-', '@', '\t', '\r'} else text


def ledger_csv(db: Session, *, user: User, filters: dict[str, Any], now: datetime | None = None) -> str:
    roles = _require_view_all(db, user)
    items = _ledger_items(db, user=user, roles=roles, filters=filters, now=now)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _key, label in CSV_COLUMNS])
    for item in items:
        row = {
            **item,
            'created_on': (item.get('created_at') or '')[:10],
            'status_label': STATUS_LABELS.get(item['status'], item['status']),
            'emergency_label': '是' if item['is_emergency'] else '',
            'overdue_label': '是' if item['is_overdue'] else '',
        }
        writer.writerow([_csv_cell(row.get(key)) for key, _label in CSV_COLUMNS])
    log_action(
        db, user_id=user.id, user_name=user.name, action='procurement_ledger_export', module='procurement',
        table_name='procurement_requests', new_value={'rows': len(items), 'filters': {k: str(v) for k, v in filters.items() if v not in (None, '')}},
    )
    return '﻿' + buffer.getvalue()


def void_request(db: Session, *, request_id: int, user: User, reason: str | None) -> ProcurementRequest:
    roles = service.user_roles(db, user)
    if not service.can_void(user, roles):
        raise service.ProcurementError(403, '只有采购科负责人和管理员能作废')
    clean_reason = (reason or '').strip()
    if not clean_reason:
        raise service.ProcurementError(422, '作废须写明理由')
    request = db.query(ProcurementRequest).filter(ProcurementRequest.id == request_id).with_for_update().first()
    if request is None:
        raise service.ProcurementError(404, '找不到这张申请单')
    if request.status != flow.STATUS_OPEN:
        raise service.ProcurementError(409, '这张申请单已经办结')
    if request.current_step == 'payment_booking':
        raise service.ProcurementError(409, '已审批付款，不能作废')
    from_step = request.current_step
    request.status = flow.STATUS_CANCELLED
    service._log(db, request, user, step=from_step, action='void', to_step=flow.STATUS_CANCELLED, comment=clean_reason, payload={})
    db.flush()
    return request


def list_suppliers(db: Session, *, user: User) -> list[dict]:
    _require_view_all(db, user)
    quotes: dict[str, dict[str, int]] = defaultdict(lambda: {'quotes': 0, 'wins': 0})
    for name, selected in db.query(ProcurementQuote.supplier, ProcurementQuote.is_selected).all():
        key = service.normalize_supplier(name)
        quotes[key]['quotes'] += 1
        quotes[key]['wins'] += 1 if selected else 0
    amounts: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    for row in db.query(ProcurementRequest).filter(ProcurementRequest.supplier.isnot(None), ProcurementRequest.status != flow.STATUS_CANCELLED).all():
        amounts[service.normalize_supplier(row.supplier)] += service.effective_amount(row)
    rows = db.query(ProcurementSupplier).order_by(ProcurementSupplier.status, ProcurementSupplier.name).all()
    return [
        {
            'id': row.id, 'name': row.name, 'status': row.status, 'contact': row.contact, 'remark': row.remark,
            'quote_count': quotes[row.normalized_name]['quotes'], 'win_count': quotes[row.normalized_name]['wins'],
            'total_amount': str(amounts[row.normalized_name]),
        }
        for row in rows
    ]


def save_supplier(db: Session, *, user: User, data: dict, supplier_id: int | None = None) -> ProcurementSupplier:
    roles = service.user_roles(db, user)
    if not service.can_edit_suppliers(user, roles):
        raise service.ProcurementError(403, '只有采购科负责人和管理员能修改供应商')
    status = data.get('status') or flow.SUPPLIER_PENDING
    if status not in SUPPLIER_STATUSES:
        raise service.ProcurementError(422, '供应商状态不对')
    name = ' '.join(str(data.get('name') or '').split())
    if not name:
        raise service.ProcurementError(422, '请填写供应商名称')
    normalized = service.normalize_supplier(name)
    if len(name) > service.SUPPLIER_NAME_LIMIT or len(normalized) > service.SUPPLIER_NAME_LIMIT:
        raise service.ProcurementError(422, f'供应商名称不能超过 {service.SUPPLIER_NAME_LIMIT} 个字')
    duplicate = db.query(ProcurementSupplier).filter(ProcurementSupplier.normalized_name == normalized).first()
    if supplier_id is None:
        if duplicate is not None:
            raise service.ProcurementError(409, '这家供应商已经有了')
        supplier = ProcurementSupplier(name=name, normalized_name=normalized)
        db.add(supplier)
        old = None
    else:
        supplier = db.get(ProcurementSupplier, supplier_id)
        if supplier is None:
            raise service.ProcurementError(404, '找不到这家供应商')
        if duplicate is not None and duplicate.id != supplier.id:
            raise service.ProcurementError(409, '这家供应商已经有了')
        old = {'name': supplier.name, 'status': supplier.status}
    supplier.name = name
    supplier.normalized_name = normalized
    supplier.status = status
    supplier.contact = (data.get('contact') or '').strip() or None
    supplier.remark = (data.get('remark') or '').strip() or None
    supplier.updated_by = user.id
    db.flush()
    log_action(
        db, user_id=user.id, user_name=user.name, action='procurement_supplier_save', module='procurement',
        table_name='procurement_suppliers', record_id=supplier.id, old_value=old, new_value={'name': name, 'status': status}, auto_commit=False,
    )
    return supplier


def board_extras(db: Session, *, now: datetime | None = None) -> dict:
    """总览里的金额分布和环节耗时。"""
    current = local_now(now)
    rows = db.query(ProcurementRequest).filter(ProcurementRequest.status.notin_(NOT_PURCHASED)).all()
    month = current.strftime('%Y-%m')
    by_category: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    by_supplier: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    backfill_overdue = 0
    for row in rows:
        amount = service.effective_amount(row)
        if service._aware(row.created_at).astimezone(current.tzinfo).strftime('%Y-%m') == month:
            by_category[row.category] += amount
        if row.supplier and row.approved_amount is not None:
            by_supplier[row.supplier] += amount
        if (row.is_emergency and row.status == flow.STATUS_OPEN and row.backfill_due_on and current.date() > row.backfill_due_on
                and not (row.details or {}).get('signed')):
            backfill_overdue += 1
    return {
        'month_by_category': [
            {'category': key, 'amount': str(value)}
            for key, value in sorted(by_category.items(), key=lambda pair: pair[1], reverse=True)
        ],
        'top_suppliers': [
            {'supplier': key, 'amount': str(value)}
            for key, value in sorted(by_supplier.items(), key=lambda pair: pair[1], reverse=True)[:10]
        ],
        'emergency_backfill_overdue': backfill_overdue,
        'step_hours': _step_hours(db, since=current - timedelta(days=90)),
    }


def _step_hours(db: Session, *, since: datetime) -> list[dict]:
    logs = db.query(ProcurementStepLog).order_by(ProcurementStepLog.request_id, ProcurementStepLog.id).all()
    spans: dict[str, list[float]] = defaultdict(list)
    previous: ProcurementStepLog | None = None
    for log in logs:
        if previous is not None and previous.request_id == log.request_id and log.action != 'upload':
            started, ended = service._aware(previous.created_at), service._aware(log.created_at)
            if ended >= since:
                spans[log.step].append((ended - started).total_seconds() / 3600)
        if log.action != 'upload':
            previous = log
    result = []
    for step in flow.STEPS:
        values = spans.get(step.code)
        if values:
            result.append({'step': step.code, 'label': step.label, 'hours': round(sum(values) / len(values), 1), 'count': len(values)})
    return result
