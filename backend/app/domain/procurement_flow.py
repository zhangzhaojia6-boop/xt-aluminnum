"""《物资采购管理办法》的 16 个环节和判定规则。只有规则，不碰数据库。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

SMALL_PURCHASE_LIMIT = Decimal('5000')
THREE_QUOTES_LIMIT = Decimal('50000')
EMERGENCY_LIMIT = Decimal('200000')
EMERGENCY_BACKFILL_WORKDAYS = 3

PROCUREMENT_ONLY_ROLE = 'procurement_staff'
ROLE_WORKSHOP_DIRECTOR = 'workshop_director'
ROLE_REQUESTER = 'requester'
ROLE_EQUIPMENT = 'equipment'
ROLE_WAREHOUSE = 'warehouse'
ROLE_PURCHASING = 'purchasing'
ROLE_PURCHASING_LEAD = 'purchasing_lead'
ROLE_DIVISION_LEAD = 'division_lead'
ROLE_GENERAL_MANAGER = 'general_manager'
ROLE_LEGAL = 'legal'
ROLE_FINANCE = 'finance'
ROLE_ACCOUNTANT = 'accountant'
ROLE_GATE = 'gate'
ROLE_QUALITY = 'quality'
ROLE_AUDIT = 'audit'

ASSIGNABLE_ROLES = {
    ROLE_EQUIPMENT: '设备部',
    ROLE_WAREHOUSE: '仓库管理员',
    ROLE_PURCHASING: '采购经办人',
    ROLE_PURCHASING_LEAD: '采购科负责人',
    ROLE_DIVISION_LEAD: '分管领导',
    ROLE_GENERAL_MANAGER: '总经理',
    ROLE_LEGAL: '法务',
    ROLE_FINANCE: '财务部',
    ROLE_ACCOUNTANT: '会计',
    ROLE_GATE: '门岗',
    ROLE_QUALITY: '质检',
    ROLE_AUDIT: '企管',
}

CATEGORIES = ('原材料', '备品备件', '设备配件', '工装工具', '劳保用品', '维修耗材')
TECH_REVIEW_CATEGORIES = {'设备配件', '维修耗材'}


@dataclass(frozen=True)
class Step:
    code: str
    number: int
    label: str
    role: str
    workdays: int | None = None
    hours: int | None = None


STEPS = (
    Step('draft', 1, '提报需求', ROLE_REQUESTER),
    Step('workshop_approval', 2, '车间审批', ROLE_WORKSHOP_DIRECTOR),
    Step('tech_review', 3, '技术审核', ROLE_EQUIPMENT),
    Step('stock_review', 4, '库存复核', ROLE_WAREHOUSE, workdays=0),
    Step('quotation', 5, '询价比价', ROLE_PURCHASING),
    Step('quotation_confirm', 5, '比价确认', ROLE_PURCHASING_LEAD),
    Step('exemption_approval', 5, '询价豁免审批', ROLE_DIVISION_LEAD),
    Step('purchase_approval', 6, '采购审批', ROLE_DIVISION_LEAD),
    Step('contract_draft', 7, '拟定合同', ROLE_PURCHASING),
    Step('legal_review', 8, '法务审核', ROLE_LEGAL, workdays=2),
    Step('finance_contract_review', 9, '财务审核合同', ROLE_FINANCE, workdays=1),
    Step('contract_sign', 10, '签订合同', ROLE_PURCHASING),
    Step('gate_registration', 11, '进厂登记', ROLE_GATE),
    Step('acceptance', 12, '验收入库', ROLE_WAREHOUSE, workdays=0),
    Step('quality_check', 12, '质检验收', ROLE_QUALITY, hours=24),
    Step('document_collection', 13, '归集资料', ROLE_PURCHASING),
    Step('payment_review', 14, '付款审核', ROLE_FINANCE, workdays=5),
    Step('payment_approval', 15, '付款审批', ROLE_GENERAL_MANAGER),
    Step('payment_booking', 16, '付款入账', ROLE_ACCOUNTANT),
    Step('emergency_consent', 1, '紧急采购超限同意', ROLE_GENERAL_MANAGER),
)
STEP_BY_CODE = {step.code: step for step in STEPS}

STATUS_OPEN = 'open'
STATUS_ARCHIVED = 'archived'
STATUS_CLOSED_STOCK = 'closed_stock'
STATUS_CANCELLED = 'cancelled'

# 九类单据。auto 表示系统在办理对应环节时自动生成。
DOCUMENT_TYPES = (
    ('request_form', '物资采购/维修申请单', 'auto'),
    ('comparison', '采购比价表或询价豁免审批单', 'auto'),
    ('contract', '审核签订的采购合同或采购订单', 'upload'),
    ('gate_note', '门岗到货单', 'auto'),
    ('delivery_note', '供应商送货单', 'upload'),
    ('receipt', '仓库入库单', 'auto'),
    ('quality_record', '质检合格证明或验收记录', 'auto'),
    ('invoice', '增值税发票', 'upload'),
    ('payment_request', '付款申请单', 'auto'),
)
UPLOAD_TYPES = {'quote', 'contract_draft', 'contract', 'gate_photo', 'delivery_note', 'invoice', 'rejection_note', 'emergency_report'}


def required_quote_count(amount: Decimal) -> int:
    """第七条：5000 以下留存记录（1 家），5000 及以上 2 家，5 万及以上 3 家。"""
    if amount >= THREE_QUOTES_LIMIT:
        return 3
    if amount >= SMALL_PURCHASE_LIMIT:
        return 2
    return 1


def purchase_approver_role(amount: Decimal) -> str:
    """第九条：5000 以下分管领导，5000 及以上总经理。"""
    return ROLE_DIVISION_LEAD if amount < SMALL_PURCHASE_LIMIT else ROLE_GENERAL_MANAGER


def can_use_order(amount: Decimal) -> bool:
    """第十条：5000 以下可用采购订单代替合同，不经法务。"""
    return amount < SMALL_PURCHASE_LIMIT


def needs_tech_review(category: str) -> bool:
    return category in TECH_REVIEW_CATEGORIES


def required_documents(*, needs_quality: bool) -> list[str]:
    return [code for code, _label, _kind in DOCUMENT_TYPES if needs_quality or code != 'quality_record']


def missing_documents(present: set[str], *, needs_quality: bool) -> list[str]:
    """付款申请单在本环节提交时生成，所以不算缺件。"""
    return [code for code in required_documents(needs_quality=needs_quality) if code != 'payment_request' and code not in present]


def add_workdays(start: date, days: int) -> date:
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def step_deadline(step: Step, entered_at: datetime) -> datetime | None:
    if step.hours is not None:
        return entered_at + timedelta(hours=step.hours)
    if step.workdays is None:
        return None
    end = add_workdays(entered_at.date(), step.workdays)
    return datetime.combine(end, datetime.max.time().replace(microsecond=0), tzinfo=entered_at.tzinfo)


def split_order_warnings(rows: list[dict], *, window_days: int = 30) -> list[dict]:
    """第七条严禁拆分：同物料同供应商窗口内多笔都不足 5000，合计却达到 5000。只提示，不拦截。"""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        amount = row.get('amount')
        if amount is None or amount >= SMALL_PURCHASE_LIMIT or not row.get('supplier'):
            continue
        groups.setdefault((row['material_name'], row['supplier']), []).append(row)
    warnings = []
    for (material, supplier), items in groups.items():
        items.sort(key=lambda item: item['created_at'])
        for index, item in enumerate(items):
            window = [
                other for other in items[index:]
                if (other['created_at'] - item['created_at']).days <= window_days
            ]
            total = sum((other['amount'] for other in window), Decimal('0'))
            if len(window) >= 2 and total >= SMALL_PURCHASE_LIMIT:
                warnings.append({
                    'material_name': material,
                    'supplier': supplier,
                    'total_amount': total,
                    'request_nos': [other['request_no'] for other in window],
                })
                break
    return warnings
