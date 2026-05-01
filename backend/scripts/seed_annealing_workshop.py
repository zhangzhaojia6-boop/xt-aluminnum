"""Seed the ZXTF (在线退火) workshop, role QR codes, and machine-line operator QR codes."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Equipment, Workshop

WORKSHOP_CODE = 'ZXTF'
WORKSHOP_NAME = '在线退火车间'
WORKSHOP_TYPE = 'annealing'

ROLE_SUFFIXES = [
    ('OP', '主操'),
    ('EN', '电工'),
    ('MT', '机修'),
]

MACHINE_LINES = [
    ('1', '1#'),
    ('2', '2#'),
    ('3', '3#'),
    ('4', '4#'),
]


def main():
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        ws = db.query(Workshop).filter(Workshop.code == WORKSHOP_CODE).first()
        if ws is None:
            ws = Workshop(
                code=WORKSHOP_CODE,
                name=WORKSHOP_NAME,
                workshop_type=WORKSHOP_TYPE,
                sort_order=200,
                is_active=True,
            )
            db.add(ws)
            db.flush()
            print(f'Created workshop: {WORKSHOP_NAME} ({WORKSHOP_CODE})')
        else:
            print(f'Workshop {WORKSHOP_CODE} already exists (id={ws.id})')

        created = 0

        ws_qr = f'XT-{WORKSHOP_CODE}-WS'
        if not db.query(Equipment).filter(Equipment.qr_code == ws_qr).first():
            db.add(Equipment(
                code=f'{WORKSHOP_CODE}-WS',
                name=f'{WORKSHOP_NAME} 车间入口',
                workshop_id=ws.id,
                equipment_type='virtual_workshop_qr',
                operational_status='running',
                qr_code=ws_qr,
                sort_order=9999,
            ))
            created += 1
            print(f'  created {ws_qr}')

        for suffix, label in ROLE_SUFFIXES:
            qr_code = f'XT-{WORKSHOP_CODE}-{suffix}'
            if db.query(Equipment).filter(Equipment.qr_code == qr_code).first():
                print(f'  skip {qr_code} (exists)')
                continue
            db.add(Equipment(
                code=f'{WORKSHOP_CODE}-{suffix}',
                name=f'{WORKSHOP_NAME} {label}',
                workshop_id=ws.id,
                equipment_type='virtual_role_qr',
                operational_status='running',
                qr_code=qr_code,
                sort_order=9990,
            ))
            created += 1
            print(f'  created {qr_code}')

        for line_code, line_name in MACHINE_LINES:
            qr_code = f'XT-{WORKSHOP_CODE}-{line_code}-OP'
            if db.query(Equipment).filter(Equipment.qr_code == qr_code).first():
                print(f'  skip {qr_code} (exists)')
                continue
            db.add(Equipment(
                code=f'{WORKSHOP_CODE}-{line_code}-OP',
                name=f'{WORKSHOP_NAME} {line_name} 主操',
                workshop_id=ws.id,
                equipment_type='virtual_role_qr',
                operational_status='running',
                qr_code=qr_code,
                sort_order=9980,
            ))
            created += 1
            print(f'  created {qr_code} -> {WORKSHOP_NAME} {line_name} 主操')

        db.commit()
        print(f'Done. Created {created} records for {WORKSHOP_NAME}.')

        print('\n=== QR Code Values ===')
        print(f'车间入口: XT-{WORKSHOP_CODE}-WS')
        for suffix, label in ROLE_SUFFIXES:
            print(f'{label}: XT-{WORKSHOP_CODE}-{suffix}')
        for line_code, line_name in MACHINE_LINES:
            print(f'{line_name} 主操: XT-{WORKSHOP_CODE}-{line_code}-OP')
    finally:
        db.close()


if __name__ == '__main__':
    main()
