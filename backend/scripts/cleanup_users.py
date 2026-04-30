# -*- coding: utf-8 -*-
"""Remove non-essential user accounts, keeping only test-necessary ones.

Keeps:
  - admin account (INIT_ADMIN_USERNAME from settings)
  - Multi-role seed accounts: {workshop_code}-EN/MT/HY/CS/QC/WG
  - Factory-level accounts: FACTORY-UM, FACTORY-IK, FACTORY-CT
  - Machine-bound operator accounts (bound_user_id references)
  - shift_leader accounts (one per workshop for legacy testing)

Usage: python -m scripts.cleanup_users
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.database import get_sessionmaker
from app.models.master import Equipment
from app.models.system import User


FACTORY_USERNAMES = {'FACTORY-UM', 'FACTORY-IK', 'FACTORY-CT'}
WORKSHOP_SUFFIXES = {'-EN', '-MT', '-HY', '-CS', '-QC', '-WG'}
KEEP_ROLES = {'admin', 'shift_leader', 'machine_operator'}


def should_keep(user, bound_user_ids: set) -> bool:
    if user.username == settings.INIT_ADMIN_USERNAME:
        return True
    if user.id in bound_user_ids:
        return True
    if user.username in FACTORY_USERNAMES:
        return True
    if any(user.username.endswith(s) for s in WORKSHOP_SUFFIXES):
        return True
    if user.role in KEEP_ROLES:
        return True
    return False


def main() -> None:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        bound_user_ids = set(
            uid for (uid,) in db.query(Equipment.bound_user_id)
            .filter(Equipment.bound_user_id.isnot(None)).all()
        )

        users = db.query(User).all()
        removed = 0
        kept = 0
        for u in users:
            if should_keep(u, bound_user_ids):
                kept += 1
                print(f'  keep: {u.username} ({u.role})')
            else:
                db.delete(u)
                removed += 1
                print(f'  remove: {u.username} ({u.role})')

        db.commit()
        print(f'\nDone. Kept {kept}, removed {removed}.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
