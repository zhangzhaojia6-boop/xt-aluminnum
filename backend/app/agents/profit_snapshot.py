"""ProfitSnapshotAgent 阶段 1：按车间 × 合金算昨日加工利润。

加工费收入 = output_weight(吨) × 加工费/吨（ProcessingFeeRule）
加工成本 = MachineDailyCostSnapshot（按车间）
毛利 = 收入 - 成本

阶段 1 限制：
- 车间 -> 默认合金的映射在 executive_constants；实际牌号从 WorkOrder 关联（阶段 2）
- 查加工费走 processing_fee_service（阻断风格：查不到挂 has_missing_fee_rule）
- is_estimated=True
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.models.executive import MachineDailyCostSnapshot, MachineDailyProfitSnapshot
from app.models.master import Workshop
from app.models.production import MobileShiftReport
from app.services.executive_constants import (
    DEFAULT_CUSTOMER_TIER,
    FALLBACK_ALLOY_GRADE,
    FALLBACK_PROCESS_TYPE,
    WORKSHOP_DEFAULT_PRODUCT,
)
from app.services.processing_fee_service import (
    MissingFeeRuleError,
    quote_processing_fee,
)


class ProfitSnapshotAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='profit_snapshot_agent')

    def execute(
        self,
        *,
        db: Session,
        target_date: Optional[date] = None,
    ) -> list[AgentDecision]:
        target_date = target_date or date.today()
        self._decisions.clear()

        # 汇总昨日每车间产量
        reports = list(
            db.execute(
                select(MobileShiftReport).where(
                    MobileShiftReport.business_date == target_date,
                    MobileShiftReport.report_status.in_(['approved', 'auto_confirmed']),
                )
            ).scalars().all()
        )
        if not reports:
            self.logger.info('No shift reports for %s; skipping profit snapshot', target_date)
            return []

        workshop_output: dict[int, Decimal] = {}
        for r in reports:
            if r.output_weight is None:
                continue
            workshop_output[r.workshop_id] = (
                workshop_output.get(r.workshop_id, Decimal('0'))
                + Decimal(str(r.output_weight))
            )

        # 查车间映射（workshop_type -> 默认合金）
        workshops_map = {
            w.id: w
            for w in db.execute(select(Workshop).where(Workshop.is_active.is_(True))).scalars().all()
        }

        for workshop_id, output_kg in workshop_output.items():
            # output_weight 单位是 kg，折算吨
            output_tons = output_kg / Decimal('1000')
            if output_tons <= 0:
                continue

            workshop = workshops_map.get(workshop_id)
            alloy, process = _lookup_default_product(workshop)

            # 查加工成本（车间粒度）
            cost = db.execute(
                select(MachineDailyCostSnapshot).where(
                    MachineDailyCostSnapshot.business_date == target_date,
                    MachineDailyCostSnapshot.workshop_id == workshop_id,
                    MachineDailyCostSnapshot.machine_line_id.is_(None),
                )
            ).scalar_one_or_none()
            total_cost = Decimal(str(cost.total_cost)) if cost else Decimal('0')

            has_missing = False
            fee_per_ton: Optional[Decimal] = None
            note_parts: list[str] = []
            try:
                quote = quote_processing_fee(
                    db,
                    customer_tier=DEFAULT_CUSTOMER_TIER,
                    alloy_grade=alloy,
                    process_type=process,
                    temper=None,
                    thickness_mm=None,
                    length_mm=None,
                    width_mm=None,
                    business_date=target_date,
                )
                fee_per_ton = quote.total_fee
                if quote.surcharges:
                    note_parts.append(
                        '附加费: ' + ', '.join(f'{s[0]}+{s[1]}' for s in quote.surcharges)
                    )
            except MissingFeeRuleError as exc:
                has_missing = True
                note_parts.append(f'无加工费规则: {exc.reason} spec={exc.spec}')

            revenue = (fee_per_ton or Decimal('0')) * output_tons
            if has_missing:
                gross_profit = None
                gross_margin_pct = None
            else:
                gross_profit = revenue - total_cost
                gross_margin_pct = (
                    (gross_profit / revenue * Decimal('100'))
                    if revenue > 0
                    else None
                )

            existing = db.execute(
                select(MachineDailyProfitSnapshot).where(
                    MachineDailyProfitSnapshot.business_date == target_date,
                    MachineDailyProfitSnapshot.workshop_id == workshop_id,
                    MachineDailyProfitSnapshot.machine_line_id.is_(None),
                    MachineDailyProfitSnapshot.alloy_grade == alloy,
                )
            ).scalar_one_or_none()
            payload = {
                'process_type': process,
                'output_tons': output_tons,
                'processing_fee_per_ton': fee_per_ton,
                'processing_revenue': revenue,
                'total_cost': total_cost,
                'gross_profit': gross_profit,
                'gross_margin_pct': gross_margin_pct,
                'is_estimated': True,
                'has_missing_fee_rule': has_missing,
                'estimation_note': (
                    '阶段 1 估算：车间粒度 × 默认合金映射。'
                    + (' ' + '; '.join(note_parts) if note_parts else '')
                ),
            }
            if existing is None:
                rec = MachineDailyProfitSnapshot(
                    business_date=target_date,
                    workshop_id=workshop_id,
                    machine_line_id=None,
                    alloy_grade=alloy,
                    **payload,
                )
                db.add(rec)
                db.flush()
                rec_id = rec.id
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                rec_id = existing.id

            self.record_decision(
                action=AgentAction.AUTO_AGGREGATE,
                target_type='machine_daily_profit_snapshot',
                target_id=rec_id,
                reason='profit_snapshot_stage1',
                business_date=target_date.isoformat(),
                workshop_id=workshop_id,
                alloy_grade=alloy,
                output_tons=str(output_tons),
                revenue=str(revenue),
                cost=str(total_cost),
                gross_profit=str(gross_profit) if gross_profit is not None else None,
                has_missing_fee_rule=has_missing,
            )

        return self._decisions


def _lookup_default_product(workshop) -> tuple[str, str]:
    if workshop is None:
        return FALLBACK_ALLOY_GRADE, FALLBACK_PROCESS_TYPE
    wt = (workshop.workshop_type or '').lower()
    if wt in WORKSHOP_DEFAULT_PRODUCT:
        return WORKSHOP_DEFAULT_PRODUCT[wt]
    code = (workshop.code or '').lower()
    name = (workshop.name or '')
    for key, mapping in WORKSHOP_DEFAULT_PRODUCT.items():
        if key in code or key in wt:
            return mapping
    if '铸' in name:
        return WORKSHOP_DEFAULT_PRODUCT['casting']
    if '冷' in name:
        return WORKSHOP_DEFAULT_PRODUCT['cold_rolling']
    if '热' in name:
        return WORKSHOP_DEFAULT_PRODUCT['hot_rolling']
    if '挤' in name:
        return WORKSHOP_DEFAULT_PRODUCT['extrusion']
    return FALLBACK_ALLOY_GRADE, FALLBACK_PROCESS_TYPE


profit_snapshot_agent = ProfitSnapshotAgent()


__all__ = ['ProfitSnapshotAgent', 'profit_snapshot_agent']
