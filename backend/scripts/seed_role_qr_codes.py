"""Generate role-level virtual equipment records with QR codes (XT-{ws}-{ROLE})."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Equipment, Workshop

ROLE_SUFFIXES = [
    ('OP', '主操'),
    ('EN', '电工'),
    ('HY', '液压'),
    ('MT', '机修'),
]


def main():
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        workshops = db.query(Workshop).all()
        created = 0
        for ws in workshops:
            for suffix, label in ROLE_SUFFIXES:
                qr_code = f'XT-{ws.code}-{suffix}'
                exists = db.query(Equipment).filter(Equipment.qr_code == qr_code).first()
                if exists:
                    print(f'  skip {qr_code} (exists)')
                    continue
                eq = Equipment(
                    code=f'{ws.code}-{suffix}',
                    name=f'{ws.name} {label}',
                    workshop_id=ws.id,
                    equipment_type='virtual_role_qr',
                    operational_status='running',
                    qr_code=qr_code,
                    sort_order=9990,
                )
                db.add(eq)
                created += 1
                print(f'  created {qr_code}')
        db.commit()
        print(f'Done. Created {created} role QR codes.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
