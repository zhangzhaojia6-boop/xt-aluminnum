# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.master import Equipment, Team, Workshop
from app.models.system import User

LEGACY_USER_IDS = {2, 4, 5}
LEGACY_USERNAMES = {'leader_demo', 'leader_round12_demo', 'leader_round12_demo_b'}
LEGACY_WORKSHOP_ID = 1
LEGACY_TEAM_ID = 1


def _count_fk_references(db, *, target_table: str, target_id: int) -> list[tuple[str, str, int]]:
    bind = db.get_bind()
    if bind is None:
        return []

    inspector = inspect(bind)
    references: list[tuple[str, str, int]] = []
    for table_name in inspector.get_table_names():
        for foreign_key in inspector.get_foreign_keys(table_name):
            if foreign_key.get('referred_table') != target_table:
                continue
            constrained_columns = foreign_key.get('constrained_columns') or []
            for column_name in constrained_columns:
                stmt = text(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{column_name}" = :target_id')
                count = int(db.execute(stmt, {'target_id': target_id}).scalar() or 0)
                if count > 0:
                    references.append((table_name, column_name, count))
    return references


def _print_references(label: str, references: list[tuple[str, str, int]]) -> None:
    if not references:
        return
    print(f'skip {label}: still referenced')
    for table_name, column_name, count in references:
        print(f'  - {table_name}.{column_name}: {count}')


def _delete_legacy_users(db) -> None:
    users = (
        db.query(User)
        .filter((User.id.in_(LEGACY_USER_IDS)) | (User.username.in_(LEGACY_USERNAMES)))
        .all()
    )
    if not users:
        print('legacy users already cleaned')
        return

    for user in users:
        bound_equipment_rows = db.query(Equipment).filter(Equipment.bound_user_id == user.id).all()
        for equipment in bound_equipment_rows:
            equipment.bound_user_id = None

        references = _count_fk_references(db, target_table='users', target_id=user.id)
        references = [item for item in references if item[0] != 'equipment']
        if references:
            user.is_active = False
            if not user.username.endswith('_legacy_disabled'):
                user.username = f'{user.username}_legacy_disabled'
            print(f'deactivated user {user.id} ({user.username}) due to references')
            _print_references(f'user {user.id}', references)
            continue

        db.delete(user)
        print(f'deleted user {user.id} ({user.username})')


def _cleanup_team_if_unused(db) -> None:
    team = db.get(Team, LEGACY_TEAM_ID)
    if team is None:
        print(f'team {LEGACY_TEAM_ID} already removed')
        return

    references = _count_fk_references(db, target_table='teams', target_id=team.id)
    references = [item for item in references if item[0] != 'teams']
    if references:
        _print_references(f'team {team.id}', references)
        return

    db.delete(team)
    print(f'deleted team {team.id}')


def _cleanup_workshop_if_unused(db) -> None:
    workshop = db.get(Workshop, LEGACY_WORKSHOP_ID)
    if workshop is None:
        print(f'workshop {LEGACY_WORKSHOP_ID} already removed')
        return

    references = _count_fk_references(db, target_table='workshops', target_id=workshop.id)
    references = [item for item in references if item[0] not in {'workshops', 'teams'}]
    if references:
        _print_references(f'workshop {workshop.id}', references)
        return

    if db.query(Team).filter(Team.workshop_id == workshop.id).first() is not None:
        print(f'skip workshop {workshop.id}: team rows still exist')
        return

    db.delete(workshop)
    print(f'deleted workshop {workshop.id}')


def main() -> None:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        _delete_legacy_users(db)
        db.flush()
        _cleanup_team_if_unused(db)
        db.flush()
        _cleanup_workshop_if_unused(db)
        db.commit()
        print('legacy cleanup finished')
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
