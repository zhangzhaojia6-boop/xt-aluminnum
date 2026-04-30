# -*- coding: utf-8 -*-
"""Seed multi-role accounts for all workshops.

Idempotent: skips accounts that already exist.
Usage: python -m scripts.seed_multi_role_accounts
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.auth import get_password_hash
from app.core.workshop_templates import WORKSHOP_TYPE_BY_WORKSHOP_CODE
from app.database import get_sessionmaker
from app.models.master import Workshop
from app.models.system import User

WORKSHOP_ROLES = [
    ('energy_stat', 'EN', '电工'),
    ('maintenance_lead', 'MT', '机修'),
    ('hydraulic_lead', 'HY', '液压'),
    ('consumable_stat', 'CS', '耗材统计'),
    ('qc', 'QC', '质检'),
    ('weigher', 'WG', '称重'),
]

FACTORY_ROLES = [
    ('utility_manager', 'FACTORY-UM', '水电气负责人'),
    ('inventory_keeper', 'FACTORY-IK', '成品库负责人'),
    ('contracts', 'FACTORY-CT', '计划科'),
]

DEFAULT_PASSWORD = 'xt123456'


def main() -> None:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        pw_hash = get_password_hash(DEFAULT_PASSWORD)
        created = 0
        skipped = 0

        workshops = db.query(Workshop).all()
        ws_by_code = {}
        for ws in workshops:
            code = ws.code or ''
            if code in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
                ws_by_code[code] = ws

        for ws_code, ws in ws_by_code.items():
            for role, suffix, label in WORKSHOP_ROLES:
                username = f'{ws_code}-{suffix}'
                existing = db.query(User).filter(User.username == username).first()
                if existing:
                    skipped += 1
                    continue
                user = User(
                    username=username,
                    password_hash=pw_hash,
                    name=f'{ws.name}{label}',
                    role=role,
                    workshop_id=ws.id,
                    is_mobile_user=True,
                    data_scope_type='own_workshop',
                )
                db.add(user)
                created += 1

        for role, username, label in FACTORY_ROLES:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                skipped += 1
                continue
            user = User(
                username=username,
                password_hash=pw_hash,
                name=label,
                role=role,
                is_mobile_user=True,
                data_scope_type='factory',
            )
            db.add(user)
            created += 1

        db.commit()
        print(f'done: {created} created, {skipped} skipped')
    finally:
        db.close()


if __name__ == '__main__':
    main()
