"""Integration test: CostAggregator + ProfitSnapshot end-to-end."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.cost_aggregator import cost_aggregator_agent
from app.agents.profit_snapshot import profit_snapshot_agent
from app.database import Base
from app.models.executive import (
    AluminumPriceDaily,
    MachineDailyCostSnapshot,
    MachineDailyProfitSnapshot,
    ProcessingFeeRule,
    ProcessingFeeSurcharge,
)
from app.models.master import Workshop, Team, Equipment
from app.models.production import MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.executive_service import build_executive_dashboard


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'exec.db'}", future=True)
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        Workshop.__table__,
        Team.__table__,
        Equipment.__table__,
        ShiftConfig.__table__,
        MobileShiftReport.__table__,
        AluminumPriceDaily.__table__,
        ProcessingFeeRule.__table__,
        ProcessingFeeSurcharge.__table__,
        MachineDailyCostSnapshot.__table__,
        MachineDailyProfitSnapshot.__table__,
    ])
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def test_profit_snapshot_end_to_end(tmp_path):
    Session = build_session(tmp_path)
    target = date(2026, 5, 8)

    with Session() as db:
        ws_hot = Workshop(code='HOT_ROLL', name='热轧车间', workshop_type='hot_rolling', is_active=True)
        ws_cold = Workshop(code='COLD_ROLL', name='冷轧车间', workshop_type='cold_rolling', is_active=True)
        db.add_all([ws_hot, ws_cold])
        db.flush()

        shift = ShiftConfig(code='DAY', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(16, 0), workshop_id=ws_hot.id)
        db.add(shift)
        db.flush()

        # 加工费规则
        db.add(ProcessingFeeRule(
            customer_tier='default',
            alloy_grade='5052',
            process_type='hot_rolling',
            fee_per_ton=Decimal('2600'),
            is_vat_inclusive=True,
            effective_from=date(2026, 1, 1),
        ))
        db.add(ProcessingFeeRule(
            customer_tier='default',
            alloy_grade='3003',
            process_type='cold_rolling',
            fee_per_ton=Decimal('1800'),
            is_vat_inclusive=True,
            effective_from=date(2026, 1, 1),
        ))
        db.commit()

        # 模拟两个车间昨日班报
        db.add(MobileShiftReport(
            business_date=target,
            shift_config_id=shift.id,
            workshop_id=ws_hot.id,
            attendance_count=10,
            output_weight=Decimal('50000'),  # 50 吨
            electricity_daily=Decimal('8000'),
            gas_daily=Decimal('2000'),
            report_status='approved',
        ))
        db.add(MobileShiftReport(
            business_date=target,
            shift_config_id=shift.id,
            workshop_id=ws_cold.id,
            team_id=None,
            attendance_count=8,
            output_weight=Decimal('30000'),  # 30 吨
            electricity_daily=Decimal('5000'),
            gas_daily=Decimal('0'),
            report_status='auto_confirmed',
        ))
        db.commit()

        # 跑 CostAggregator
        cost_decisions = cost_aggregator_agent.execute(db=db, target_date=target)
        db.flush()
        assert len(cost_decisions) == 2

        # 跑 ProfitSnapshot
        profit_decisions = profit_snapshot_agent.execute(db=db, target_date=target)
        db.commit()
        assert len(profit_decisions) == 2

        # 验证车间 hot_rolling 毛利
        hot_snap = db.query(MachineDailyProfitSnapshot).filter_by(
            workshop_id=ws_hot.id, business_date=target,
        ).one()
        # 收入 = 50 吨 × 2600 = 130000
        assert Decimal(str(hot_snap.processing_revenue)) == Decimal('130000')
        # 成本 = 8000×0.8 + 2000×3.6 + 10×350 = 6400 + 7200 + 3500 = 17100
        assert Decimal(str(hot_snap.total_cost)) == Decimal('17100')
        # 毛利 = 130000 - 17100 = 112900
        assert Decimal(str(hot_snap.gross_profit)) == Decimal('112900')
        assert hot_snap.has_missing_fee_rule is False

        # 验证车间 cold_rolling 毛利 (30 吨 × 1800)
        cold_snap = db.query(MachineDailyProfitSnapshot).filter_by(
            workshop_id=ws_cold.id, business_date=target,
        ).one()
        assert Decimal(str(cold_snap.processing_revenue)) == Decimal('54000')
        # 成本 = 5000×0.8 + 0 + 8×350 = 4000 + 2800 = 6800
        assert Decimal(str(cold_snap.total_cost)) == Decimal('6800')
        assert Decimal(str(cold_snap.gross_profit)) == Decimal('47200')

        # 驾驶舱聚合
        dash = build_executive_dashboard(db, business_date=target)
        assert dash['total_profit'] == 160100.0  # 112900 + 47200
        assert dash['total_revenue'] == 184000.0
        assert dash['total_cost'] == 23900.0
        assert len(dash['workshops']) == 2
        # 热轧毛利高排第一
        assert dash['workshops'][0]['workshop_id'] == ws_hot.id
        assert dash['is_estimated'] is True


def test_missing_fee_rule_does_not_crash(tmp_path):
    """不配加工费时 ProfitSnapshot 应挂 has_missing_fee_rule, 不进合计。"""

    Session = build_session(tmp_path)
    target = date(2026, 5, 8)

    with Session() as db:
        ws = Workshop(code='WEIRD', name='某车间', workshop_type='unknown', is_active=True)
        db.add(ws)
        db.flush()
        shift = ShiftConfig(code='DAY', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(16, 0), workshop_id=ws.id)
        db.add(shift)
        db.flush()

        db.add(MobileShiftReport(
            business_date=target,
            shift_config_id=shift.id,
            workshop_id=ws.id,
            attendance_count=5,
            output_weight=Decimal('10000'),
            electricity_daily=Decimal('500'),
            gas_daily=Decimal('100'),
            report_status='approved',
        ))
        db.commit()

        cost_aggregator_agent.execute(db=db, target_date=target)
        db.flush()
        profit_snapshot_agent.execute(db=db, target_date=target)
        db.commit()

        snap = db.query(MachineDailyProfitSnapshot).filter_by(
            workshop_id=ws.id, business_date=target,
        ).one()
        assert snap.has_missing_fee_rule is True
        assert snap.gross_profit is None

        dash = build_executive_dashboard(db, business_date=target)
        assert dash['has_missing_fee_rule'] is True
        assert dash['total_profit'] == 0.0
