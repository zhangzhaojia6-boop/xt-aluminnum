# -*- coding: utf-8 -*-
"""Soft-deactivate workshops outside the current production scope."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import OperationalError


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.active_workshops import (  # noqa: E402
    is_active_production_workshop_code,
    is_active_production_workshop_name,
    normalize_workshop_name,
)
from app.database import get_sessionmaker  # noqa: E402
from app.models.master import Equipment, Team, Workshop  # noqa: E402
from app.models.system import User  # noqa: E402


KEEP_SUPPORT_NAMES = {'成品库', '回收车间'}
KEEP_SUPPORT_CODES = {'CPK', 'FINISHED', 'STORAGE', 'HS'}


def _code(value: str | None) -> str:
    return str(value or '').strip().upper()


def should_keep_workshop(workshop: Workshop) -> tuple[bool, str]:
    if not workshop.is_active:
        return True, '保留：原本未启用'
    if is_active_production_workshop_code(workshop.code) or is_active_production_workshop_name(workshop.name):
        return True, '保留：13个生产车间'
    if normalize_workshop_name(workshop.name) in KEEP_SUPPORT_NAMES or _code(workshop.code) in KEEP_SUPPORT_CODES:
        return True, '保留：内勤/成品库/回收/专项填报入口'
    return False, '停用：不在生产车间和成品库范围'


def cleanup_unused_workshops(*, apply: bool) -> dict[str, int | list[dict[str, str | int]]]:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    changed: list[dict[str, str | int]] = []
    kept = 0
    try:
        workshops = db.query(Workshop).order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()
        for workshop in workshops:
            keep, reason = should_keep_workshop(workshop)
            if keep:
                kept += 1
                print(f'keep {workshop.code} {workshop.name}: {reason}')
                continue

            equipment_count = db.query(Equipment).filter(
                Equipment.workshop_id == workshop.id,
                Equipment.is_active.is_(True),
            ).count()
            team_count = db.query(Team).filter(
                Team.workshop_id == workshop.id,
                Team.is_active.is_(True),
            ).count()
            user_count = db.query(User).filter(
                User.workshop_id == workshop.id,
                User.is_active.is_(True),
            ).count()
            changed.append({
                'id': workshop.id,
                'code': workshop.code,
                'name': workshop.name,
                'equipment_count': equipment_count,
                'team_count': team_count,
                'user_count': user_count,
            })
            print(f'deactivate {workshop.code} {workshop.name}: {reason}')

            if apply:
                workshop.is_active = False
                db.query(Equipment).filter(Equipment.workshop_id == workshop.id).update(
                    {Equipment.is_active: False},
                    synchronize_session=False,
                )
                db.query(Team).filter(Team.workshop_id == workshop.id).update(
                    {Team.is_active: False},
                    synchronize_session=False,
                )
                db.query(User).filter(User.workshop_id == workshop.id).update(
                    {User.is_active: False},
                    synchronize_session=False,
                )

        if apply:
            db.commit()
        else:
            db.rollback()
        return {
            'kept': kept,
            'changed_count': len(changed),
            'changed': changed,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        result = cleanup_unused_workshops(apply=args.apply)
    except OperationalError as error:
        raise SystemExit(f'数据库连接失败，未修改任何数据：{error.orig}') from error
    mode = 'APPLY' if args.apply else 'DRY_RUN'
    print(f'{mode}: kept={result["kept"]}, changed={result["changed_count"]}')


if __name__ == '__main__':
    main()
