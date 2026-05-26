"""Seed 5/26 test data matching 5/24 truth-source totals.

Inserts shift_production_data rows (A/B/C per workshop) plus a small set of
mobile_coil work_order_entries to exercise pass_count MTD cards. Re-run safe:
deletes any prior test rows for business_date=2026-05-26 first.

Usage on prod:
    cd /srv/aluminum-bypass/backend
    .venv/bin/python scripts/seed_test_data_2026_05_26.py
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import get_sessionmaker  # noqa: E402
from app.models.master import Equipment, Workshop  # noqa: E402
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry  # noqa: E402
from app.models.shift import ShiftConfig  # noqa: E402
from app.models.system import User  # noqa: E402

TARGET_DATE = date(2026, 5, 26)
SEED_TAG = 'seed_5_26_test'
random.seed(20260526)

# 5/24 真值底（吨/度/m³）—— 三班合计目标。
WORKSHOP_TOTALS = {
    'ZD':     {'output': 309, 'electricity': 7941, 'gas': 25687},
    'ZR2':    {'output': 25,  'electricity': 558,  'gas': 2527},
    'ZR3':    {'output': 40,  'electricity': 901,  'gas': 4130},
    'RZ':     {'output': 244, 'electricity': 31479,'gas': 4475},
    'LZ1650': {'output': 137, 'electricity': 15906},
    'LZ1850': {'output': 0,   'electricity': 0},
    'LZ2050': {'output': 88,  'electricity': 22695},
    'JZ':     {'output': 114, 'electricity': 935},
    'JQ':     {'output': 109, 'electricity': 1624},
    'LJ':     {'output': 190, 'electricity': 3135},
    'ZXTF':   {'output': 199, 'electricity': 15283, 'gas': 1183},
    'CH':     {'output': 0,   'electricity': 0},
    'HS':     {'output': 62,  'electricity': 0,    'gas': 1411},
}

# 道次（5/24 真值）—— mobile_coil entries used for MTD pass_count.
PASS_COUNT_BY_WS = {'LZ1650': 55, 'LZ1850': 0, 'LZ2050': 73}

SHIFT_SPLIT = (0.35, 0.40, 0.25)  # A/B/C 比例


def split_three(total: float) -> list[float]:
    a = round(total * SHIFT_SPLIT[0], 3)
    b = round(total * SHIFT_SPLIT[1], 3)
    c = round(total - a - b, 3)
    return [a, b, c]


def main() -> None:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        workshops = {w.code: w for w in db.query(Workshop).all()}
        shifts = {s.code: s for s in db.query(ShiftConfig).filter(ShiftConfig.code.in_(['A', 'B', 'C'])).all()}
        if set(shifts) != {'A', 'B', 'C'}:
            raise SystemExit(f'Shift configs missing — got {set(shifts)}')
        admin = db.query(User).filter(User.username == 'admin').first()
        if not admin:
            raise SystemExit('admin user missing')

        # Clean prior seed rows for idempotency.
        deleted = db.query(ShiftProductionData).filter(
            ShiftProductionData.business_date == TARGET_DATE,
            ShiftProductionData.notes == SEED_TAG,
        ).delete(synchronize_session=False)
        woe_q = db.query(WorkOrderEntry).filter(
            WorkOrderEntry.business_date == TARGET_DATE,
            WorkOrderEntry.entry_type == 'mobile_coil',
        )
        wo_ids = [r.work_order_id for r in woe_q.all()]
        woe_q.delete(synchronize_session=False)
        if wo_ids:
            db.query(WorkOrder).filter(
                WorkOrder.id.in_(wo_ids),
                WorkOrder.tracking_card_no.like('TEST526-%'),
            ).delete(synchronize_session=False)
        print(f'Cleared {deleted} prior shift rows + {len(wo_ids)} prior mobile_coil entries')

        # Pick canonical equipment per workshop (first non-virtual active).
        eq_by_ws: dict[int, Equipment] = {}
        for eq in db.query(Equipment).filter(Equipment.is_active == True).order_by(Equipment.workshop_id, Equipment.sort_order, Equipment.id).all():  # noqa: E712
            if (eq.equipment_type or '').startswith('virtual_'):
                continue
            eq_by_ws.setdefault(eq.workshop_id, eq)

        inserted = 0
        for code, totals in WORKSHOP_TOTALS.items():
            ws = workshops.get(code)
            if not ws:
                print(f'  skip {code} — workshop missing')
                continue
            eq = eq_by_ws.get(ws.id)
            outs = split_three(totals['output'])
            ins = [round(v / 0.84, 3) for v in outs]
            scrap = [round(i - o, 3) for i, o in zip(ins, outs)]
            elec = split_three(totals.get('electricity', 0))
            for shift_code, out_v, in_v, sc_v, e_v in zip(['A', 'B', 'C'], outs, ins, scrap, elec):
                row = ShiftProductionData(
                    workshop_id=ws.id,
                    equipment_id=eq.id if eq else None,
                    shift_config_id=shifts[shift_code].id,
                    business_date=TARGET_DATE,
                    input_weight=in_v,
                    output_weight=out_v,
                    qualified_weight=out_v,
                    scrap_weight=sc_v,
                    electricity_kwh=e_v,
                    downtime_minutes=0,
                    issue_count=0,
                    data_source='mobile',
                    data_status='confirmed',
                    notes=SEED_TAG,
                    version_no=1,
                    confirmed_by=admin.id,
                    confirmed_at=datetime.now(timezone.utc),
                )
                db.add(row)
                inserted += 1

        # mobile_coil entries for道次 MTD.
        coil_inserted = 0
        for code, day_passes in PASS_COUNT_BY_WS.items():
            ws = workshops.get(code)
            if not ws or day_passes <= 0:
                continue
            eq = eq_by_ws.get(ws.id)
            # split into 3 shifts of one coil each (kg = output*1000).
            outs_t = split_three(WORKSHOP_TOTALS[code]['output'])
            passes = split_three(day_passes)
            for idx, (shift_code, out_t, p) in enumerate(zip(['A', 'B', 'C'], outs_t, passes)):
                if out_t <= 0 and p <= 0:
                    continue
                tracking_no = f'TEST526-{code}-{shift_code}-{idx+1}'
                wo = WorkOrder(
                    tracking_card_no=tracking_no,
                    process_route_code='COLD_ROLL',
                    overall_status='in_progress',
                    created_by=admin.id,
                )
                db.add(wo)
                db.flush()
                entry = WorkOrderEntry(
                    work_order_id=wo.id,
                    workshop_id=ws.id,
                    machine_id=eq.id if eq else None,
                    shift_id=shifts[shift_code].id,
                    business_date=TARGET_DATE,
                    on_machine_time=time(0, 0),
                    off_machine_time=time(8, 0),
                    input_weight=int(round(out_t / 0.84 * 1000)),
                    output_weight=int(round(out_t * 1000)),
                    scrap_weight=int(round((out_t / 0.84 - out_t) * 1000)),
                    entry_type='mobile_coil',
                    entry_status='approved',
                    submitted_at=datetime.now(timezone.utc),
                    verified_at=datetime.now(timezone.utc),
                    approved_at=datetime.now(timezone.utc),
                    created_by=admin.id,
                    created_by_user_id=admin.id,
                    extra_payload={
                        'pass_count': int(p),
                        'process_stage': '成品' if code == 'LZ2050' else '中退',
                    },
                )
                db.add(entry)
                coil_inserted += 1

        db.commit()
        print(f'Inserted {inserted} shift rows + {coil_inserted} mobile_coil entries for {TARGET_DATE}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
