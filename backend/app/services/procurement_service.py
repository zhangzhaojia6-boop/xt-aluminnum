"""物资采购 16 环节办理。规则在 app/domain/procurement_flow.py。"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.core.business_time import local_now
from app.domain import procurement_flow as flow
from app.services.agent_communication_service import AgentCommunicationError, queue_bound_message
from app.models.procurement import (
    ProcurementAssignment,
    ProcurementDocument,
    ProcurementQuote,
    ProcurementRequest,
    ProcurementStepLog,
    ProcurementSupplier,
)
from app.models.system import User

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
NOTIFY_AGENT = 'factory_dispatch_zzj'
NOTIFY_CHANNEL_TYPE = 'dingtalk_work_notice'
logger = logging.getLogger(__name__)
ALLOWED_SUFFIXES = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}


class ProcurementError(Exception):
    def __init__(self, status_code: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.extra = extra


def _reject(message: str, **extra: Any) -> ProcurementError:
    return ProcurementError(422, message, **extra)


def _decimal(value: Any, label: str, *, allow_zero: bool = False) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _reject(f'{label}不是有效数字') from None
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero):
        raise _reject(f'{label}必须大于 0')
    return number


def _text(payload: dict, key: str, label: str) -> str:
    value = str(payload.get(key) or '').strip()
    if not value:
        raise _reject(f'请填写{label}')
    return value


def user_roles(db: Session, user: User) -> set[str]:
    roles = {row.role for row in db.query(ProcurementAssignment).filter(ProcurementAssignment.user_id == user.id).all()}
    if user.role == flow.ROLE_WORKSHOP_DIRECTOR:
        roles.add(flow.ROLE_WORKSHOP_DIRECTOR)
    return roles


def can_view_all(user: User, roles: set[str]) -> bool:
    return user.role == 'admin' or bool(roles & flow.VIEW_ALL_ROLES)


def can_void(user: User, roles: set[str]) -> bool:
    return user.role == 'admin' or flow.ROLE_PURCHASING_LEAD in roles


def can_edit_suppliers(user: User, roles: set[str]) -> bool:
    return user.role == 'admin' or flow.ROLE_PURCHASING_LEAD in roles


def can_open(db: Session, user: User, roles: set[str], request: ProcurementRequest) -> bool:
    """当前办理人和办过这张单的人也能打开。"""
    if can_view(user, roles, request) or can_act(user, roles, request):
        return True
    return db.query(ProcurementStepLog.id).filter(ProcurementStepLog.request_id == request.id, ProcurementStepLog.actor_id == user.id).first() is not None


def normalize_supplier(name: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', name or '')).casefold()


def _ensure_supplier_allowed(db: Session, name: str) -> None:
    """黑名单不再合作；第一次出现的供应商记为待评价。"""
    key = normalize_supplier(name)
    supplier = db.query(ProcurementSupplier).filter(ProcurementSupplier.normalized_name == key).first()
    if supplier is None:
        db.add(ProcurementSupplier(name=' '.join(name.split()), normalized_name=key, status=flow.SUPPLIER_PENDING))
        db.flush()
    elif supplier.status == flow.SUPPLIER_BLACKLISTED:
        raise _reject(f'{supplier.name} 在黑名单里，不能合作')


def effective_amount(request: ProcurementRequest) -> Decimal:
    if request.approved_amount is not None:
        return Decimal(request.approved_amount)
    quantity = Decimal(request.purchase_quantity if request.purchase_quantity is not None else request.quantity)
    return (quantity * Decimal(request.estimated_unit_price)).quantize(Decimal('0.01'))


def step_role(request: ProcurementRequest) -> str:
    if request.current_step == 'purchase_approval':
        return flow.purchase_approver_role(effective_amount(request))
    return flow.STEP_BY_CODE[request.current_step].role


def can_act(user: User, roles: set[str], request: ProcurementRequest) -> bool:
    if request.status != flow.STATUS_OPEN:
        return False
    role = step_role(request)
    if role == flow.ROLE_REQUESTER:
        return request.requester_id == user.id
    if role == flow.ROLE_WORKSHOP_DIRECTOR:
        return flow.ROLE_WORKSHOP_DIRECTOR in roles and user.workshop_id == request.workshop_id
    return role in roles


def can_view(user: User, roles: set[str], request: ProcurementRequest) -> bool:
    if can_view_all(user, roles) or request.requester_id == user.id:
        return True
    return flow.ROLE_WORKSHOP_DIRECTOR in roles and user.workshop_id == request.workshop_id


def _move(request: ProcurementRequest, step: str, now: datetime) -> None:
    request.current_step = step
    request.step_entered_at = now


def _details(request: ProcurementRequest, key: str, value: dict) -> None:
    request.details = {**(request.details or {}), key: value}


def _has_document(db: Session, request: ProcurementRequest, doc_type: str) -> bool:
    return db.query(ProcurementDocument.id).filter(
        ProcurementDocument.request_id == request.id,
        ProcurementDocument.doc_type == doc_type,
    ).first() is not None


def create_request(db: Session, *, user: User, data: dict, now: datetime | None = None) -> ProcurementRequest:
    current = local_now(now)
    category = _text(data, 'category', '物资类别')
    if category not in flow.CATEGORIES:
        raise _reject('物资类别不在办法规定的范围内')
    request = ProcurementRequest(
        trace_id=f'procurement:{uuid4().hex}',
        requester_id=user.id,
        workshop_id=user.workshop_id,
        material_name=_text(data, 'material_name', '物料名称'),
        specification=str(data.get('specification') or '').strip() or None,
        unit=_text(data, 'unit', '单位'),
        category=category,
        quantity=_decimal(data.get('quantity'), '数量'),
        estimated_unit_price=_decimal(data.get('estimated_unit_price'), '预估单价'),
        needed_by=data.get('needed_by') or None,
        purpose=_text(data, 'purpose', '用途'),
        is_emergency=bool(data.get('is_emergency')),
        current_step='draft',
        status=flow.STATUS_OPEN,
        step_entered_at=current,
        details={},
    )
    db.add(request)
    db.flush()
    request.request_no = f'CG{current:%Y%m%d}{request.id:04d}'
    _log(db, request, user, step='draft', action='create', to_step='draft', comment=None, payload={})
    db.flush()
    return request


def _log(db: Session, request: ProcurementRequest, user: User, *, step: str, action: str, to_step: str | None, comment: str | None, payload: dict) -> None:
    db.add(ProcurementStepLog(
        request_id=request.id,
        step=step,
        action=action,
        to_step=to_step,
        actor_id=user.id,
        actor_name=user.name,
        comment=comment,
        payload=_json_safe(payload),
    ))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def _after_contract(request: ProcurementRequest, now: datetime) -> None:
    """紧急采购的货已经进厂，补完手续后直接归集资料。"""
    if (request.details or {}).get('acceptance'):
        _move(request, 'document_collection', now)
    else:
        _move(request, 'gate_registration', now)


def _submit(db, request, user, payload, now):
    if request.is_emergency:
        report = _text(payload, 'emergency_report', '向分管领导电话报告的记录')
        _details(request, 'emergency', {'report': report, 'reported_at': now.isoformat()})
        if effective_amount(request) > flow.EMERGENCY_LIMIT:
            _move(request, 'emergency_consent', now)
        else:
            _move(request, 'gate_registration', now)
        return
    _move(request, 'workshop_approval', now)


def _approve_workshop(db, request, user, payload, now):
    _move(request, 'tech_review' if flow.needs_tech_review(request.category) else 'stock_review', now)


def _approve_tech(db, request, user, payload, now):
    _move(request, 'stock_review', now)


def _confirm_stock(db, request, user, payload, now):
    stock = _decimal(payload.get('stock_quantity'), '库存数量', allow_zero=True)
    available = _decimal(payload.get('available_quantity', stock), '可领用数量', allow_zero=True)
    if available > stock:
        raise _reject('可领用数量不能大于库存数量')
    quantity = Decimal(request.quantity)
    _details(request, 'stock', {'stock_quantity': str(stock), 'available_quantity': str(available)})
    if available >= quantity:
        request.status = flow.STATUS_CLOSED_STOCK
        return
    request.purchase_quantity = quantity - available
    _move(request, 'quotation', now)


def _submit_quotes(db, request, user, payload, now):
    quotes = payload.get('quotes') or []
    selected = payload.get('selected_index')
    if not isinstance(selected, int) or not 0 <= selected < len(quotes):
        raise _reject('请选定一家供应商')
    purchase_quantity = Decimal(request.purchase_quantity if request.purchase_quantity is not None else request.quantity)
    parsed = [(_text(item, 'supplier', '供应商'), _decimal(item.get('unit_price'), '报价'), item.get('remark')) for item in quotes]
    if len({supplier for supplier, _price, _remark in parsed}) != len(parsed):
        raise _reject('同一家供应商只算一家报价')
    amount = (purchase_quantity * parsed[selected][1]).quantize(Decimal('0.01'))
    # 按选定金额和申请预估金额中较大的算，防止压低选定价绕开询价
    estimated = purchase_quantity * Decimal(request.estimated_unit_price)
    required = flow.required_quote_count(max(amount, estimated))
    if len(parsed) < required:
        raise _reject(f'本次金额需要不少于 {required} 家有效报价，当前 {len(parsed)} 家', required=required, actual=len(parsed))
    for supplier, _price, _remark in parsed:
        _ensure_supplier_allowed(db, supplier)
    round_no = 1 + db.query(ProcurementQuote).filter(ProcurementQuote.request_id == request.id).count()
    for index, (supplier, price, remark) in enumerate(parsed):
        db.add(ProcurementQuote(
            request_id=request.id, round_no=round_no, supplier=supplier, unit_price=price,
            is_selected=index == selected, remark=remark, created_by=user.id,
        ))
    request.supplier = parsed[selected][0]
    request.approved_amount = amount
    _details(request, 'comparison', {'kind': 'quotes', 'required': required, 'count': len(parsed), 'round': round_no})
    _move(request, 'quotation_confirm' if amount >= flow.SMALL_PURCHASE_LIMIT else 'purchase_approval', now)


def _request_exemption(db, request, user, payload, now):
    reason = _text(payload, 'reason', '豁免理由')
    if reason not in {'独家供应', '生产线紧急抢修', '年度框架协议'}:
        raise _reject('豁免理由只能是独家供应、生产线紧急抢修或年度框架协议')
    purchase_quantity = Decimal(request.purchase_quantity if request.purchase_quantity is not None else request.quantity)
    price = _decimal(payload.get('unit_price'), '单价')
    request.supplier = _text(payload, 'supplier', '供应商')
    _ensure_supplier_allowed(db, request.supplier)
    request.approved_amount = (purchase_quantity * price).quantize(Decimal('0.01'))
    _details(request, 'comparison', {'kind': 'exemption', 'reason': reason})
    _move(request, 'exemption_approval', now)


def _to_purchase_approval(db, request, user, payload, now):
    _move(request, 'purchase_approval', now)


def _approve_purchase(db, request, user, payload, now):
    _move(request, 'contract_draft', now)


def _submit_contract(db, request, user, payload, now):
    doc_kind = payload.get('doc_kind')
    amount = _decimal(payload.get('amount'), '合同金额')
    if doc_kind == 'order':
        if not flow.can_use_order(effective_amount(request)):
            raise _reject('5000 元及以上须签合同，不能用采购订单')
    elif doc_kind == 'contract':
        if not _has_document(db, request, 'contract_draft'):
            raise _reject('请先上传合同稿')
    else:
        raise _reject('请选择合同或采购订单')
    if amount > effective_amount(request):
        raise _reject('合同金额超过已审批金额，请退回重新审批')
    _details(request, 'contract', {
        'doc_kind': doc_kind,
        'contract_no': _text(payload, 'contract_no', '合同或订单编号'),
        'amount': str(amount),
        'standard_text': bool(payload.get('standard_text')),
    })
    _move(request, 'finance_contract_review' if doc_kind == 'order' else 'legal_review', now)


def _approve_legal(db, request, user, payload, now):
    _move(request, 'finance_contract_review', now)


def _approve_finance_contract(db, request, user, payload, now):
    contract = {**(request.details or {}).get('contract', {}), 'signing_entity': _text(payload, 'signing_entity', '签约主体')}
    _details(request, 'contract', contract)
    _move(request, 'contract_sign', now)


def _sign_contract(db, request, user, payload, now):
    if (request.details or {}).get('contract', {}).get('doc_kind') == 'contract' and not _has_document(db, request, 'contract'):
        raise _reject('请先上传盖章合同')
    _details(request, 'signed', {'signed_at': now.isoformat()})
    _after_contract(request, now)


def _register_gate(db, request, user, payload, now):
    _details(request, 'gate', {
        'supplier': _text(payload, 'supplier', '送货单位'),
        'goods': _text(payload, 'goods', '货物名称'),
        'quantity': str(_decimal(payload.get('quantity'), '送货数量')),
        'plate_no': _text(payload, 'plate_no', '车牌号'),
        'entered_at': now.isoformat(),
    })
    _move(request, 'acceptance', now)


def _finish_receipt(request, now):
    if request.is_emergency and not (request.details or {}).get('signed'):
        request.backfill_due_on = flow.add_workdays(now.date(), flow.EMERGENCY_BACKFILL_WORKDAYS)
        _move(request, 'quotation', now)
        return
    _move(request, 'document_collection', now)


def _accept(db, request, user, payload, now):
    accepted = _decimal(payload.get('accepted_quantity'), '验收数量')
    request.needs_quality_check = bool(payload.get('needs_quality_check'))
    _details(request, 'acceptance', {'accepted_quantity': str(accepted), 'accepted_at': now.isoformat(), 'receipt_no': f'RK{request.request_no}'})
    if request.needs_quality_check:
        _move(request, 'quality_check', now)
    else:
        _finish_receipt(request, now)


def _refuse_delivery(db, request, user, payload, now):
    if not _has_document(db, request, 'rejection_note'):
        raise _reject('请先上传供应商签字的拒收说明')
    _details(request, 'rejection', {'reason': _text(payload, 'reason', '拒收原因'), 'at': now.isoformat()})
    details = dict(request.details)
    details.pop('gate', None)
    details.pop('acceptance', None)
    request.details = details
    _move(request, 'gate_registration', now)


def _pass_quality(db, request, user, payload, now):
    _details(request, 'quality', {'result': 'pass', 'at': now.isoformat(), 'by': user.name})
    _finish_receipt(request, now)


def present_documents(db: Session, request: ProcurementRequest) -> set[str]:
    details = request.details or {}
    present = {row[0] for row in db.query(ProcurementDocument.doc_type).filter(ProcurementDocument.request_id == request.id).all()}
    present.add('request_form')
    if details.get('comparison'):
        present.add('comparison')
    if details.get('contract', {}).get('doc_kind') == 'order':
        present.add('contract')
    if details.get('gate'):
        present.add('gate_note')
    if details.get('acceptance'):
        present.add('receipt')
    if details.get('quality'):
        present.add('quality_record')
    if details.get('payment_request'):
        present.add('payment_request')
    return present


def _submit_payment(db, request, user, payload, now):
    missing = flow.missing_documents(present_documents(db, request), needs_quality=request.needs_quality_check)
    if missing:
        raise _reject('单据不齐，不能发起付款', missing=missing)
    invoice_amount = _decimal(payload.get('invoice_amount'), '发票金额')
    payment_amount = _decimal(payload.get('payment_amount'), '付款金额')
    contract_amount = Decimal((request.details or {}).get('contract', {}).get('amount', '0'))
    differences = []
    if invoice_amount != contract_amount:
        differences.append(f'发票金额 {invoice_amount} 与合同金额 {contract_amount} 不一致')
    if payment_amount > invoice_amount:
        differences.append(f'付款金额 {payment_amount} 大于发票金额 {invoice_amount}')
    if differences:
        raise _reject('；'.join(differences), differences=differences)
    _details(request, 'payment_request', {
        'invoice_no': _text(payload, 'invoice_no', '发票号'),
        'invoice_amount': str(invoice_amount),
        'payment_amount': str(payment_amount),
    })
    _move(request, 'payment_review', now)


def _approve_payment_review(db, request, user, payload, now):
    _move(request, 'payment_approval', now)


def _approve_payment(db, request, user, payload, now):
    _move(request, 'payment_booking', now)


def _book_payment(db, request, user, payload, now):
    voucher = _text(payload, 'voucher_no', '凭证号')
    request.paid_amount = Decimal((request.details or {}).get('payment_request', {}).get('payment_amount', '0'))
    _details(request, 'payment', {'voucher_no': voucher, 'paid_at': now.isoformat()})
    request.status = flow.STATUS_ARCHIVED


def _cancel(db, request, user, payload, now):
    request.status = flow.STATUS_CANCELLED


def _back(step: str):
    def handler(db, request, user, payload, now):
        _move(request, step, now)
    return handler


def _emergency_consent(db, request, user, payload, now):
    _move(request, 'gate_registration', now)


# 驳回必须写理由；退回上一个有权修改的环节，不直接作废。
ACTIONS: dict[str, dict[str, Any]] = {
    'draft': {'submit': _submit, 'cancel': _cancel},
    'emergency_consent': {'approve': _emergency_consent, 'reject': _back('draft')},
    'workshop_approval': {'approve': _approve_workshop, 'reject': _back('draft')},
    'tech_review': {'approve': _approve_tech, 'reject': _back('draft')},
    'stock_review': {'confirm_stock': _confirm_stock},
    'quotation': {'submit_quotes': _submit_quotes, 'request_exemption': _request_exemption},
    'quotation_confirm': {'approve': _to_purchase_approval, 'reject': _back('quotation')},
    'exemption_approval': {'approve': _to_purchase_approval, 'reject': _back('quotation')},
    'purchase_approval': {'approve': _approve_purchase, 'reject': _back('quotation')},
    'contract_draft': {'submit_contract': _submit_contract},
    'legal_review': {'approve': _approve_legal, 'reject': _back('contract_draft')},
    'finance_contract_review': {'approve': _approve_finance_contract, 'reject': _back('contract_draft')},
    'contract_sign': {'sign': _sign_contract},
    'gate_registration': {'register': _register_gate},
    'acceptance': {'accept': _accept, 'refuse': _refuse_delivery},
    'quality_check': {'approve': _pass_quality, 'reject': _back('gate_registration')},
    'document_collection': {'submit_payment': _submit_payment},
    'payment_review': {'approve': _approve_payment_review, 'reject': _back('document_collection')},
    'payment_approval': {'approve': _approve_payment, 'reject': _back('document_collection')},
    'payment_booking': {'book': _book_payment},
}


def apply_action(
    db: Session,
    *,
    request_id: int,
    user: User,
    action: str,
    expected_step: str,
    comment: str | None = None,
    payload: dict | None = None,
    now: datetime | None = None,
) -> ProcurementRequest:
    request = db.query(ProcurementRequest).filter(ProcurementRequest.id == request_id).with_for_update().first()
    if request is None:
        raise ProcurementError(404, '找不到这张申请单')
    if request.status != flow.STATUS_OPEN:
        raise ProcurementError(409, '这张申请单已经办结')
    if request.current_step != expected_step:
        raise ProcurementError(409, '这一步已被其他人办理，请刷新后再看')
    if not can_act(user, user_roles(db, user), request):
        raise ProcurementError(403, '这一步不归你办理')
    handler = ACTIONS[request.current_step].get(action)
    if handler is None:
        raise _reject('这一步不能做这个操作')
    clean_comment = (comment or '').strip() or None
    if action == 'reject' and not clean_comment:
        raise _reject('驳回须写明理由')
    current = local_now(now)
    from_step = request.current_step
    data = payload or {}
    handler(db, request, user, data, current)
    _log(
        db, request, user, step=from_step, action=action,
        to_step=request.current_step if request.status == flow.STATUS_OPEN else request.status,
        comment=clean_comment, payload=data,
    )
    db.flush()
    if request.status == flow.STATUS_OPEN and request.current_step != from_step:
        _notify_step_owners(db, request)
    return request


def channel_key_for(user_id: int) -> str:
    return f'procurement-user-{user_id}'


def _step_owner_ids(db: Session, request: ProcurementRequest) -> list[int]:
    role = step_role(request)
    if role == flow.ROLE_REQUESTER:
        return [request.requester_id]
    if role == flow.ROLE_WORKSHOP_DIRECTOR:
        rows = db.query(User.id).filter(User.role == role, User.workshop_id == request.workshop_id, User.is_active.is_(True)).all()
    else:
        rows = db.query(User.id).join(ProcurementAssignment, ProcurementAssignment.user_id == User.id).filter(ProcurementAssignment.role == role, User.is_active.is_(True)).all()
    return [row[0] for row in rows]


def _notify_step_owners(db: Session, request: ProcurementRequest) -> None:
    """发给下一环节办理人。通道默认演练，没开通道的人跳过，不影响走单。"""
    step = flow.STEP_BY_CODE[request.current_step]
    content = f'{request.request_no} {request.material_name}，金额 {effective_amount(request)} 元，请办理：{step.label}\n\n/procurement/{request.id}'
    for user_id in _step_owner_ids(db, request):
        try:
            queue_bound_message(
                db,
                agent_code=NOTIFY_AGENT,
                channel_key=channel_key_for(user_id),
                channel_type=NOTIFY_CHANNEL_TYPE,
                title=f'采购待办：{step.label}',
                content=content,
                source_summary='物资采购',
                trace_id=request.trace_id,
                dedupe_key=f'procurement:{request.id}:{request.current_step}:{user_id}',
                commit=False,
            )
        except AgentCommunicationError as exc:
            logger.info('procurement_notify_skipped request=%s user=%s reason=%s', request.id, user_id, exc)


def save_document(
    db: Session,
    *,
    request_id: int,
    user: User,
    doc_type: str,
    file_name: str,
    content: bytes,
    content_type: str | None = None,
) -> ProcurementDocument:
    request = db.get(ProcurementRequest, request_id)
    if request is None:
        raise ProcurementError(404, '找不到这张申请单')
    roles = user_roles(db, user)
    if not can_act(user, roles, request):
        raise ProcurementError(403, '只有当前环节的办理人能上传单据')
    if doc_type not in flow.UPLOAD_TYPES:
        raise _reject('不支持这种单据类型')
    suffix = Path(file_name or '').suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise _reject('只能上传 PDF 或图片')
    if not content:
        raise _reject('文件是空的')
    if len(content) > MAX_UPLOAD_BYTES:
        raise _reject('文件不能超过 20MB')
    digest = hashlib.sha256(content).hexdigest()
    relative = Path('procurement') / str(request.id) / f'{uuid4().hex}{suffix}'
    target = Path(settings.UPLOAD_DIR) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    document = ProcurementDocument(
        request_id=request.id, doc_type=doc_type, file_name=Path(file_name).name[:255],
        stored_path=relative.as_posix(), content_type=content_type, size_bytes=len(content),
        sha256=digest, uploaded_by=user.id,
    )
    db.add(document)
    _log(db, request, user, step=request.current_step, action='upload', to_step=request.current_step, comment=None, payload={'doc_type': doc_type, 'sha256': digest})
    db.flush()
    return document


def document_path(document: ProcurementDocument) -> Path:
    return Path(settings.UPLOAD_DIR) / document.stored_path


def _deadline(request: ProcurementRequest) -> datetime | None:
    if request.status != flow.STATUS_OPEN:
        return None
    return flow.step_deadline(flow.STEP_BY_CODE[request.current_step], _aware(request.step_entered_at))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def serialize_request(db: Session, request: ProcurementRequest, *, user: User, roles: set[str], now: datetime | None = None, full: bool = False) -> dict:
    current = local_now(now)
    step = flow.STEP_BY_CODE[request.current_step]
    deadline = _deadline(request)
    backfill_overdue = bool(request.backfill_due_on and request.status == flow.STATUS_OPEN and not (request.details or {}).get('signed') and current.date() > request.backfill_due_on)
    data = {
        'id': request.id,
        'request_no': request.request_no,
        'material_name': request.material_name,
        'specification': request.specification,
        'unit': request.unit,
        'category': request.category,
        'quantity': str(request.quantity),
        'purchase_quantity': None if request.purchase_quantity is None else str(request.purchase_quantity),
        'estimated_unit_price': str(request.estimated_unit_price),
        'amount': str(effective_amount(request)),
        'supplier': request.supplier,
        'is_emergency': request.is_emergency,
        'status': request.status,
        'current_step': request.current_step,
        'step_number': step.number,
        'step_label': step.label,
        'step_role': step_role(request),
        'step_entered_at': _aware(request.step_entered_at).isoformat(),
        'deadline': deadline.isoformat() if deadline else None,
        'is_overdue': bool(deadline and current > deadline) or backfill_overdue,
        'backfill_due_on': request.backfill_due_on.isoformat() if request.backfill_due_on else None,
        'can_act': can_act(user, roles, request),
        'trace_id': request.trace_id,
        'created_at': _aware(request.created_at).isoformat() if request.created_at else None,
    }
    if not full:
        return data
    present = present_documents(db, request)
    needed = set(flow.required_documents(needs_quality=request.needs_quality_check))
    logs = db.query(ProcurementStepLog).filter(ProcurementStepLog.request_id == request.id).order_by(ProcurementStepLog.id).all()
    documents = db.query(ProcurementDocument).filter(ProcurementDocument.request_id == request.id).order_by(ProcurementDocument.id).all()
    quotes = db.query(ProcurementQuote).filter(ProcurementQuote.request_id == request.id).order_by(ProcurementQuote.round_no, ProcurementQuote.id).all()
    data.update(
        purpose=request.purpose,
        needed_by=request.needed_by.isoformat() if request.needed_by else None,
        details=request.details or {},
        actions=sorted(ACTIONS.get(request.current_step, {})) if data['can_act'] else [],
        can_void=can_void(user, roles) and request.status == flow.STATUS_OPEN and request.current_step != 'payment_booking',
        document_checklist=[
            {'code': code, 'label': label, 'present': code in present}
            for code, label, _kind in flow.DOCUMENT_TYPES if code in needed
        ],
        documents=[
            {'id': row.id, 'doc_type': row.doc_type, 'file_name': row.file_name, 'size_bytes': row.size_bytes, 'sha256': row.sha256}
            for row in documents
        ],
        quotes=[
            {'round_no': row.round_no, 'supplier': row.supplier, 'unit_price': str(row.unit_price), 'is_selected': row.is_selected, 'remark': row.remark}
            for row in quotes
        ],
        logs=[
            {'step': row.step, 'step_label': flow.STEP_BY_CODE[row.step].label, 'action': row.action, 'actor_name': row.actor_name, 'comment': row.comment, 'at': _aware(row.created_at).isoformat() if row.created_at else None}
            for row in logs
        ],
    )
    return data


def list_requests(db: Session, *, user: User, scope: str, now: datetime | None = None) -> list[dict]:
    roles = user_roles(db, user)
    query = db.query(ProcurementRequest).order_by(ProcurementRequest.id.desc())
    if scope == 'mine':
        rows = query.filter(ProcurementRequest.requester_id == user.id).limit(200).all()
    elif scope == 'all':
        if not can_view_all(user, roles):
            raise ProcurementError(403, '没有查看全部台账的权限')
        rows = query.limit(500).all()
    else:
        rows = [row for row in query.filter(ProcurementRequest.status == flow.STATUS_OPEN).limit(1000).all() if can_act(user, roles, row)]
    return [serialize_request(db, row, user=user, roles=roles, now=now) for row in rows]


def build_board(db: Session, *, user: User, now: datetime | None = None) -> dict:
    roles = user_roles(db, user)
    if not can_view_all(user, roles):
        raise ProcurementError(403, '没有查看全部台账的权限')
    rows = db.query(ProcurementRequest).all()
    items = [serialize_request(db, row, user=user, roles=roles, now=now) for row in rows]
    open_items = [item for item in items if item['status'] == flow.STATUS_OPEN]
    funnel = []
    seen = set()
    for step in flow.STEPS:
        if step.code == 'emergency_consent' or step.number in seen:
            continue
        seen.add(step.number)
        funnel.append({
            'number': step.number,
            'label': step.label,
            'count': sum(1 for item in open_items if item['step_number'] == step.number),
        })
    month = local_now(now).strftime('%Y-%m')
    split_rows = [
        {
            'material_name': row.material_name, 'supplier': row.supplier, 'request_no': row.request_no,
            'amount': Decimal(row.approved_amount) if row.approved_amount is not None else None,
            'created_at': _aware(row.created_at),
        }
        for row in rows if row.status != flow.STATUS_CANCELLED
    ]
    return {
        'open_count': len(open_items),
        'overdue_count': sum(1 for item in open_items if item['is_overdue']),
        'emergency_count': sum(1 for item in open_items if item['is_emergency']),
        'archived_count': sum(1 for item in items if item['status'] == flow.STATUS_ARCHIVED),
        'stock_closed_count': sum(1 for item in items if item['status'] == flow.STATUS_CLOSED_STOCK),
        'month_paid_amount': str(sum(
            (Decimal(row.paid_amount) for row in rows if row.paid_amount is not None and _aware(row.updated_at).strftime('%Y-%m') == month),
            Decimal('0'),
        )),
        'funnel': funnel,
        'overdue': [item for item in open_items if item['is_overdue']][:50],
        'split_warnings': [
            {**warning, 'total_amount': str(warning['total_amount'])}
            for warning in flow.split_order_warnings(split_rows)
        ],
    }


def list_assignments(db: Session) -> list[dict]:
    rows = db.query(ProcurementAssignment, User).join(User, User.id == ProcurementAssignment.user_id).order_by(ProcurementAssignment.role, User.name).all()
    return [{'id': row.id, 'user_id': person.id, 'user_name': person.name, 'role': row.role, 'role_label': flow.ASSIGNABLE_ROLES.get(row.role, row.role)} for row, person in rows]


def set_assignment(db: Session, *, actor: User, user_id: int, role: str, enabled: bool) -> None:
    if role not in flow.ASSIGNABLE_ROLES:
        raise _reject('没有这个岗位')
    if db.get(User, user_id) is None:
        raise ProcurementError(404, '找不到这个账号')
    existing = db.query(ProcurementAssignment).filter(ProcurementAssignment.user_id == user_id, ProcurementAssignment.role == role).first()
    if enabled and existing is None:
        db.add(ProcurementAssignment(user_id=user_id, role=role, created_by=actor.id))
    elif not enabled and existing is not None:
        db.delete(existing)
    db.flush()
