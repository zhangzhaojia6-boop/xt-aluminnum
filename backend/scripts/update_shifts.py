from datetime import time
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.shift import ShiftConfig

UPDATES = {
    "A": ("长白班", "day", time(7, 30), time(15, 30), False, 0, 1),
    "B": ("小夜班", "evening", time(15, 30), time(23, 30), False, 0, 2),
    "C": ("大夜班", "night", time(23, 30), time(7, 30), True, 0, 3),
}
LEGACY_SHIFT_CODES = {"DAY", "MID", "NIGHT"}


def main():
    db = get_sessionmaker()()
    try:
        for code, (name, shift_type, start, end, cross, offset, sort_order) in UPDATES.items():
            shift = db.query(ShiftConfig).filter(ShiftConfig.code == code).first()
            if shift is None:
                shift = ShiftConfig(code=code, workshop_id=None)
                db.add(shift)
            shift.name = name
            shift.shift_type = shift_type
            shift.start_time = start
            shift.end_time = end
            shift.is_cross_day = cross
            shift.business_day_offset = offset
            shift.sort_order = sort_order
            shift.is_active = True
            print("updated %s: %s %s-%s cross=%s" % (code, name, start, end, cross))

        for shift in db.query(ShiftConfig).filter(ShiftConfig.code.in_(LEGACY_SHIFT_CODES)).all():
            shift.is_active = False
            print("disabled legacy shift %s" % shift.code)
        db.commit()
        print("Done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
