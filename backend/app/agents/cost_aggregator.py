"""CostAggregatorAgent 阶段 1：按车间归集昨日加工成本（能耗 + 粗人工摊）。

阶段 1 限制：
- 粒度按车间，不细到机列（MobileShiftReport 没机列字段）
- 辅料成本为 0（阶段 2 等核算员录入）
- 人工成本 = 出勤人数 × 350 元/人天（粗摊，阶段 3 改按道次计件）
- is_estimated=True 全局标示

输出：`machine_daily_cost_snapshots` 每车间一行/日。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.models.executive import MachineDailyCostSnapshot
from app.models.master import Workshop
from app.models.production import MobileShiftReport
from app.services.executive_constants import (
    ELECTRICITY_PRICE_PER_KWH,
    LABOR_COST_PER_HEADCOUNT_PER_DAY,
    NATURAL_GAS_PRICE_PER_M3,
)


class CostAggregatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='cost_aggregator_agent')

    def execute(
        self,
        *,
        db: Session,
        target_date: Optional[date] = None,
    ) -> list[AgentDecision]:
        target_date = target_date or date.today()
        self._decisions.clear()

        # 拉 target_date 所有车间的班报，按 workshop_id 聚合
        stmt = select(MobileShiftReport).where(
            MobileShiftReport.business_date == target_date,
            MobileShiftReport.report_status.in_(['approved', 'auto_confirmed']),
        )
        reports = list(db.execute(stmt).scalars().all())

        if not reports:
            self.logger.info('No shift reports for %s; skipping cost aggregation', target_date)
            return []

        # workshop_id -> (kwh, m3, attendance_sum)
        agg: dict[int, dict[str, Decimal | int]] = {}
        for r in reports:
            ws = agg.setdefault(
                r.workshop_id,
                {'kwh': Decimal('0'), 'gas': Decimal('0'), 'attendance': 0},
            )
            if r.electricity_daily is not None:
                ws['kwh'] += Decimal(str(r.electricity_daily))
            if r.gas_daily is not None:
                ws['gas'] += Decimal(str(r.gas_daily))
            if r.attendance_count is not None:
                ws['attendance'] += int(r.attendance_count)

        # upsert 到 machine_daily_cost_snapshots（阶段 1：machine_line_id 留空）
        for workshop_id, stats in agg.items():
            kwh = stats['kwh']
            gas = stats['gas']
            attendance = stats['attendance']

            elec_cost = kwh * ELECTRICITY_PRICE_PER_KWH
            gas_cost = gas * NATURAL_GAS_PRICE_PER_M3
            labor_cost = Decimal(str(attendance)) * LABOR_COST_PER_HEADCOUNT_PER_DAY
            aux_cost = Decimal('0')
            total = elec_cost + gas_cost + labor_cost + aux_cost

            existing = db.execute(
                select(MachineDailyCostSnapshot).where(
                    MachineDailyCostSnapshot.business_date == target_date,
                    MachineDailyCostSnapshot.workshop_id == workshop_id,
                    MachineDailyCostSnapshot.machine_line_id.is_(None),
                )
            ).scalar_one_or_none()
            payload = {
                'electricity_kwh': kwh,
                'electricity_cost': elec_cost,
                'natural_gas_m3': gas,
                'natural_gas_cost': gas_cost,
                'labor_cost': labor_cost,
                'aux_material_cost': aux_cost,
                'total_cost': total,
                'is_estimated': True,
                'estimation_note': (
                    '阶段 1 估算：电×0.80 + 气×3.60 + 出勤人数×350元/人天，'
                    '辅料成本为 0，粒度到车间。阶段 2 补 41 项辅料和机列级归集。'
                ),
            }
            if existing is None:
                rec = MachineDailyCostSnapshot(
                    business_date=target_date,
                    workshop_id=workshop_id,
                    machine_line_id=None,
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
                target_type='machine_daily_cost_snapshot',
                target_id=rec_id,
                reason='cost_aggregated_stage1',
                business_date=target_date.isoformat(),
                workshop_id=workshop_id,
                total_cost=str(total),
                kwh=str(kwh),
                gas=str(gas),
                attendance=attendance,
            )
        return self._decisions


cost_aggregator_agent = CostAggregatorAgent()


__all__ = ['CostAggregatorAgent', 'cost_aggregator_agent']
