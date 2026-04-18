# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.bootstrap import seed_field_mapping_templates, seed_shift_configs, seed_system_configs


def main() -> None:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        seed_system_configs(db)
        seed_shift_configs(db)
        seed_field_mapping_templates(db)
        print('master data initialized')
    finally:
        db.close()


if __name__ == '__main__':
    main()
