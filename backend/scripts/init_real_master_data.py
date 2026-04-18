# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.pilot_schedule_seed import seed_default_pilot_schedule
from app.services.real_master_data import seed_real_master_data


def main() -> None:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        seed_real_master_data(db)
        seeded = seed_default_pilot_schedule(db)
        print('real master data initialized')
        print(f'default pilot schedule synced: {seeded}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
