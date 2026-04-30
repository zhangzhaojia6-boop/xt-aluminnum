"""Seed machine-line operator QR codes: XT-{ws}-{line}-OP per machine line."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Equipment, Workshop

WORKSHOP_MACHINES = {
    'ZD': [('1', '1#'), ('2', '2#'), ('3', '3#'), ('4', '4#')],
    'ZR2': [('1', '1#'), ('2', '2#'), ('3', '3#'), ('4', '4#'), ('5', '5#'), ('6', '6#')],
    'ZR3': [('1', '1#'), ('2', '2#'), ('3', '3#'), ('4', '4#'), ('5', '5#'), ('6', '6#'), ('7', '7#'), ('8', '8#'), ('9', '9#')],
    'RZ': [('SAW', '锯床'), ('FMILL', '六面铣'), ('DMILL', '双面铣'), ('MED', '中厚板'), ('HEAT', '加热炉'), ('ROLL', '热轧机')],
    'LZ2050': [('1', '2050#')],
    'LZ1450': [('1', '1450#1'), ('2', '1450#2'), ('800', '800#')],
    'LZ3': [('1', '1#'), ('2', '2#'), ('3', '3#'), ('4', '4#'), ('5', '5#')],
    'JZ': [('19R', '19辊'), ('N19R', '新19辊'), ('SL', '纵剪')],
    'JZ2': [('LJ', '拉矫'), ('DFQ', '大分切'), ('XJZ', '小剪子')],
    'JQ': [('1', '1#'), ('2', '2#'), ('3', '3#'), ('4', '4#'), ('RJ', '重卷')],
    'CPK': [],
}


def main():
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        created = 0
        for ws_code, machine_list in WORKSHOP_MACHINES.items():
            ws = db.query(Workshop).filter(Workshop.code == ws_code).first()
            if not ws:
                print(f'  skip {ws_code} (workshop not found)')
                continue
            for line_code, line_name in machine_list:
                qr_code = f'XT-{ws_code}-{line_code}-OP'
                exists = db.query(Equipment).filter(Equipment.qr_code == qr_code).first()
                if exists:
                    print(f'  skip {qr_code} (exists)')
                    continue
                eq = Equipment(
                    code=f'{ws_code}-{line_code}-OP',
                    name=f'{ws.name} {line_name} 主操',
                    workshop_id=ws.id,
                    equipment_type='virtual_role_qr',
                    operational_status='running',
                    qr_code=qr_code,
                    sort_order=9980,
                )
                db.add(eq)
                created += 1
                print(f'  created {qr_code} -> {ws.name} {line_name} 主操')
        db.commit()
        print(f'Done. Created {created} machine-line operator QR codes.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
