"""加工费查询引擎。

输入一条产品规格（客户、牌号、工艺、状态、厚度、长宽），返回含附加费的加工费/吨。
上游调用点：ProfitSnapshotAgent、加工费管理 API。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.executive import ProcessingFeeRule, ProcessingFeeSurcharge


@dataclass
class ProcessingFeeQuote:
    base_fee: Decimal
    surcharges: list[tuple[str, Decimal, str]]  # (surcharge_type, amount, note)
    total_fee: Decimal
    matched_rule_id: int
    customer_tier: str
    is_vat_inclusive: bool


class MissingFeeRuleError(Exception):
    """找不到适用的加工费规则。对应业务方案：阻断上 P&L，挂告警。"""

    def __init__(self, reason: str, spec: dict):
        super().__init__(reason)
        self.reason = reason
        self.spec = spec


def _match_thickness(rule: ProcessingFeeRule, thickness_mm: Optional[float]) -> bool:
    if rule.thickness_min_mm is None and rule.thickness_max_mm is None:
        return True
    if thickness_mm is None:
        return False
    t = Decimal(str(thickness_mm))
    lo = Decimal(str(rule.thickness_min_mm)) if rule.thickness_min_mm is not None else None
    hi = Decimal(str(rule.thickness_max_mm)) if rule.thickness_max_mm is not None else None
    if lo is not None and t < lo:
        return False
    if hi is not None and t >= hi:
        return False
    return True


def _match_surcharge_condition(
    condition: dict,
    *,
    thickness_mm: Optional[float],
    length_mm: Optional[float],
    width_mm: Optional[float],
) -> bool:
    if 'thickness_lt' in condition:
        if thickness_mm is None or thickness_mm >= condition['thickness_lt']:
            return False
    if 'thickness_gte' in condition:
        if thickness_mm is None or thickness_mm < condition['thickness_gte']:
            return False
    if 'length_min' in condition or 'length_max' in condition:
        if length_mm is None:
            return False
        if 'length_min' in condition and length_mm < condition['length_min']:
            return False
        if 'length_max' in condition and length_mm > condition['length_max']:
            return False
    if 'width_gte' in condition:
        if width_mm is None or width_mm < condition['width_gte']:
            return False
    if 'width_lt' in condition:
        if width_mm is None or width_mm >= condition['width_lt']:
            return False
    return True


def quote_processing_fee(
    db: Session,
    *,
    customer_tier: str = 'default',
    alloy_grade: str,
    process_type: str,
    temper: Optional[str] = None,
    thickness_mm: Optional[float] = None,
    length_mm: Optional[float] = None,
    width_mm: Optional[float] = None,
    business_date: date,
) -> ProcessingFeeQuote:
    """查询指定规格的加工费。

    没找到匹配的 base rule → 抛 MissingFeeRuleError。附加费按客户分层 + 条件匹配叠加。
    """

    stmt = (
        select(ProcessingFeeRule)
        .where(ProcessingFeeRule.customer_tier == customer_tier)
        .where(ProcessingFeeRule.alloy_grade == alloy_grade)
        .where(ProcessingFeeRule.process_type == process_type)
        .where(ProcessingFeeRule.effective_from <= business_date)
    )
    rules = [
        r for r in db.execute(stmt).scalars().all()
        if r.effective_to is None or r.effective_to >= business_date
    ]
    if temper is not None:
        rules = [r for r in rules if r.temper is None or r.temper == temper]
    rules = [r for r in rules if _match_thickness(r, thickness_mm)]

    # 优先选"状态精确匹配 + 厚度区间精确匹配"的规则
    rules.sort(
        key=lambda r: (
            0 if (temper is not None and r.temper == temper) else 1,
            0 if r.thickness_min_mm is not None else 1,
            -(r.effective_from.toordinal()),
        )
    )
    if not rules:
        # 回退到 default 客户分层
        if customer_tier != 'default':
            return quote_processing_fee(
                db,
                customer_tier='default',
                alloy_grade=alloy_grade,
                process_type=process_type,
                temper=temper,
                thickness_mm=thickness_mm,
                length_mm=length_mm,
                width_mm=width_mm,
                business_date=business_date,
            )
        raise MissingFeeRuleError(
            'no_matching_base_rule',
            {
                'customer_tier': customer_tier,
                'alloy_grade': alloy_grade,
                'process_type': process_type,
                'temper': temper,
                'thickness_mm': thickness_mm,
                'business_date': business_date.isoformat(),
            },
        )

    chosen = rules[0]
    base_fee = Decimal(str(chosen.fee_per_ton))

    # 叠加附加费（按客户分层查，不够则继续用 default）
    surcharge_stmt = (
        select(ProcessingFeeSurcharge)
        .where(ProcessingFeeSurcharge.customer_tier.in_([customer_tier, 'default']))
        .where(ProcessingFeeSurcharge.effective_from <= business_date)
    )
    surcharge_rows = [
        s for s in db.execute(surcharge_stmt).scalars().all()
        if s.effective_to is None or s.effective_to >= business_date
    ]
    applied: list[tuple[str, Decimal, str]] = []
    for sc in surcharge_rows:
        # 客户专属优先于 default（去重）
        if sc.customer_tier == 'default' and any(
            a.customer_tier == customer_tier
            and a.surcharge_type == sc.surcharge_type
            and a.condition_json == sc.condition_json
            for a in surcharge_rows
            if a.customer_tier != 'default'
        ):
            continue
        if _match_surcharge_condition(
            sc.condition_json or {},
            thickness_mm=thickness_mm,
            length_mm=length_mm,
            width_mm=width_mm,
        ):
            applied.append((sc.surcharge_type, Decimal(str(sc.fee_per_ton)), sc.note or ''))

    total = base_fee + sum((a[1] for a in applied), Decimal('0'))

    return ProcessingFeeQuote(
        base_fee=base_fee,
        surcharges=applied,
        total_fee=total,
        matched_rule_id=chosen.id,
        customer_tier=chosen.customer_tier,
        is_vat_inclusive=chosen.is_vat_inclusive,
    )


__all__ = ['ProcessingFeeQuote', 'MissingFeeRuleError', 'quote_processing_fee']
