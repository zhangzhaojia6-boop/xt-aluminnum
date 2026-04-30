"""Seed shift configs and set workshop_type for all workshops."""
import sys
from pathlib import Path
from datetime import time

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Workshop
from app.models.shift import ShiftConfig

WORKSHOP_TYPES = {
    'ZD': 'casting',
    'ZR2': 'casting',
    'ZR3': 'casting',
    'RZ': 'hot_roll',
    'LZ2050': 'cold_roll',
    'LZ1450': 'cold_roll',
    'LZ3': 'cold_roll',
    'JZ': 'finishing',
    'JZ2': 'finishing',
    'JQ': 'shearing',
    'CPK': 'inventory',
}

SHIFTS = [
    ('DAY', 'day', '白班', time(8, 0), time(16, 0), False, 0, 1),
    ('MID', 'mid', '中班', time(16, 0), time(0, 0), True, 0, 2),
    ('NIGHT', 'night', '夜班', time(0, 0), time(8, 0), False, -1, 3),
]


def main():
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        # Set workshop_type
        for ws in db.query(Workshop).all():
            wt = WORKSHOP_TYPES.get(ws.code)
            if wt and getattr(ws, 'workshop_type', None) != wt:
                ws.workshop_type = wt
                print("  set %s workshop_type=%s" % (ws.code, wt))

        # Create shift configs (global, not per-workshop)
        for code, shift_type, name, start, end, cross_day, biz_offset, sort in SHIFTS:
            exists = db.query(ShiftConfig).filter(ShiftConfig.code == code).first()
            if exists:
                print("  skip shift %s (exists)" % code)
                continue
            sc = ShiftConfig(
                code=code,
                name=name,
                shift_type=shift_type,
                start_time=start,
                end_time=end,
                is_cross_day=cross_day,
                business_day_offset=biz_offset,
                workshop_id=None,
                sort_order=sort,
                is_active=True,
            )
            db.add(sc)
            print("  created shift %s (%s) %s-%s" % (code, name, start, end))

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == '__main__':
    main()
