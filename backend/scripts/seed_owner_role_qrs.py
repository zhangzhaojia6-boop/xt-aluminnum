"""G14: seed virtual_role_qr Equipment rows for the 7 owner roles.

Each owner role pins to a host workshop (mostly CPK 成品库 for company-level
owners, JQ for 园区剪切, HS for 回收). After inserting Equipment rows, this
script delegates User account creation to ``seed_virtual_role_qr_accounts``
in ``app.services.real_master_data`` so the auto-bind pathway stays the
single source of truth for owner credentials.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Equipment, Workshop
from app.services.real_master_data import seed_virtual_role_qr_accounts

# (suffix, label, role identifier, host workshop code)
OWNER_ROLE_SPECS = [
    ('QM', '质检内勤', 'quality_owner', 'CPK'),
    ('PL', '计划内勤', 'planning_owner', 'CPK'),
    ('EC', '总电工', 'energy_chief', 'CPK'),
    ('FS', '成品库', 'storage_owner', 'CPK'),
    ('PSH', '园区剪切', 'shipment_outflow_owner', 'JQ'),
    ('RC', '回收', 'recovery_owner', 'HS'),
    ('OH', '大修', 'overhaul_owner', 'CPK'),
]


def main() -> int:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        # Pre-resolve host workshops; bail early if any are missing.
        host_codes = {spec[3] for spec in OWNER_ROLE_SPECS}
        workshops = {
            ws.code: ws
            for ws in db.query(Workshop).filter(Workshop.code.in_(host_codes)).all()
        }
        missing = sorted(host_codes - workshops.keys())
        if missing:
            print(f'ERROR: host workshop(s) not found: {", ".join(missing)}')
            return 1

        created = 0
        for suffix, label, _role, host_code in OWNER_ROLE_SPECS:
            ws = workshops[host_code]
            qr_code = f'XT-{ws.code}-{suffix}'
            exists = db.query(Equipment).filter(Equipment.qr_code == qr_code).first()
            if exists:
                print(f'  skip {qr_code} (exists)')
                continue
            eq = Equipment(
                code=f'{ws.code}-{suffix}',
                name=f'{ws.name}{label}',
                workshop_id=ws.id,
                equipment_type='virtual_role_qr',
                operational_status='running',
                qr_code=qr_code,
                sort_order=9991,
            )
            db.add(eq)
            created += 1
            print(f'  created {qr_code}')
        db.commit()

        # Delegate User account creation to the canonical auto-bind seeder.
        seed_virtual_role_qr_accounts(db)
        db.commit()

        print(f'Created {created} owner role QRs.')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
