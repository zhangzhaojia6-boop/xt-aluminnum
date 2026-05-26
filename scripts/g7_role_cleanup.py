"""G7 role cleanup — truth-source-three-layer-schema.md §6 step 1.

Final role matrix (§2.1):
- admin
- machine_operator (51 主操)
- shift_leader (班长, alias: team_leader / deputy_leader / mobile_user)
- energy_stat (车间级电工)
- 7 owner: quality_owner / planning_owner / energy_chief /
           storage_owner / shipment_outflow_owner / recovery_owner / overhaul_owner

Roles to deactivate (NOT in the matrix):
- qc / contracts / inventory_keeper / utility_manager:
  legacy 车间级 surrogates — replaced by 7 owner roles.
- consumable_stat:
  耗材 was always 班长 work; merge into shift_leader owner-agent (§3.2).
- mobile_user:
  legacy alias — kept as login alias only (§2.1 footnote).

Action: set is_active=false on legacy-role users; do NOT delete
(keep audit trail). Idempotent — safe to rerun.
"""

from __future__ import annotations

from sqlalchemy import update

from app.database import get_sessionmaker
from app.models.system import User


LEGACY_ROLES_DEACTIVATE = (
    'qc',
    'contracts',
    'inventory_keeper',
    'utility_manager',
    'consumable_stat',
    'mobile_user',
)


def main() -> None:
    db = get_sessionmaker()()
    try:
        before = (
            db.query(User.role, User.is_active)
            .filter(User.role.in_(LEGACY_ROLES_DEACTIVATE))
            .all()
        )
        print(f'before: {len(before)} legacy-role users')
        for role in LEGACY_ROLES_DEACTIVATE:
            cnt = sum(1 for r, _ in before if r == role)
            active_cnt = sum(1 for r, a in before if r == role and a)
            print(f'  {role}: total={cnt}, active={active_cnt}')

        result = db.execute(
            update(User)
            .where(User.role.in_(LEGACY_ROLES_DEACTIVATE))
            .where(User.is_active.is_(True))
            .values(is_active=False)
        )
        db.commit()
        print(f'deactivated: {result.rowcount} users')

        after = (
            db.query(User.role)
            .filter(User.is_active.is_(True))
            .order_by(User.role)
            .all()
        )
        from collections import Counter
        c = Counter(r for r, in after)
        print('active roles after cleanup:')
        for role, n in sorted(c.items()):
            print(f'  {role}: {n}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
