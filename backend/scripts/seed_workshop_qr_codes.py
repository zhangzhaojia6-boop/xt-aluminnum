"""Generate workshop-level virtual equipment records with QR codes (XT-{code}-WS)."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Equipment, Workshop


def main():
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        workshops = db.query(Workshop).all()
        created = 0
        for ws in workshops:
            qr_code = f'XT-{ws.code}-WS'
            exists = db.query(Equipment).filter(Equipment.qr_code == qr_code).first()
            if exists:
                print(f'  skip {qr_code} (exists)')
                continue
            eq = Equipment(
                code=f'{ws.code}-WS',
                name=f'{ws.name} 车间入口',
                workshop_id=ws.id,
                equipment_type='virtual_workshop_qr',
                operational_status='running',
                qr_code=qr_code,
                sort_order=9999,
            )
            db.add(eq)
            created += 1
            print(f'  created {qr_code}')
        db.commit()
        print(f'Done. Created {created} workshop QR codes.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
