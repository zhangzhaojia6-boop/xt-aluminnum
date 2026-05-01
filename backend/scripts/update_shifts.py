from datetime import time
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.shift import ShiftConfig

UPDATES = {
    "DAY": ("白班", time(7, 30), time(15, 30), False, 0),
    "MID": ("中班", time(15, 30), time(23, 30), False, 0),
    "NIGHT": ("夜班", time(23, 30), time(7, 30), True, -1),
}


def main():
    db = get_sessionmaker()()
    try:
        for code, (name, start, end, cross, offset) in UPDATES.items():
            shift = db.query(ShiftConfig).filter(ShiftConfig.code == code).first()
            if shift:
                shift.name = name
                shift.start_time = start
                shift.end_time = end
                shift.is_cross_day = cross
                shift.business_day_offset = offset
                print("updated %s: %s %s-%s cross=%s" % (code, name, start, end, cross))
        db.commit()
        print("Done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
