from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_password_hash, verify_password
from app.core.workshop_templates import WORKSHOP_TYPE_BY_WORKSHOP_CODE
from app.models.master import Equipment, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.equipment_service import generate_random_pin


ZR2_CUSTOM_FIELDS = [
    {'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'},
    {'name': 'cast_cut_count', 'label': '铸轧削', 'type': 'number', 'unit': '个'},
    {'name': 'al_rod', 'label': '铝棒', 'type': 'number', 'unit': '个'},
    {'name': 'fine_roll', 'label': '精轧', 'type': 'number', 'unit': '个'},
    {'name': 'coarse_roll', 'label': '粗轧', 'type': 'number', 'unit': '个'},
    {'name': 'back_plate', 'label': '背板', 'type': 'number', 'unit': '个'},
    {'name': 'tip_plate', 'label': '嘴片', 'type': 'number', 'unit': '个'},
    {'name': 'graphite_ring', 'label': '石墨环', 'type': 'number', 'unit': '个'},
    {'name': 'filter_plate', 'label': '过滤板', 'type': 'number', 'unit': '个'},
    {'name': 'silica_tube', 'label': '硅碳管', 'type': 'number', 'unit': '根'},
    {'name': 'mn_agent_kg', 'label': '锰剂', 'type': 'number', 'unit': '公斤'},
]

HOT_ROLL_CUSTOM_FIELDS = [
    {'name': 'trim_weight', 'label': '切头重量', 'type': 'number', 'unit': 'kg'},
    {'name': 'oil_consumption', 'label': '润滑油', 'type': 'number', 'unit': 'L'},
]

WORKSHOPS = [
    {'code': 'ZD', 'name': '铸锭车间', 'sort_order': 1},
    {'code': 'ZR2', 'name': '铸二车间', 'sort_order': 2},
    {'code': 'ZR3', 'name': '铸三车间', 'sort_order': 3},
    {'code': 'RZ', 'name': '热轧车间', 'sort_order': 4},
    {'code': 'LZ2050', 'name': '2050冷轧车间', 'sort_order': 5},
    {'code': 'LZ1450', 'name': '1450冷轧车间', 'sort_order': 6},
    {'code': 'LZ3', 'name': '冷轧三车间', 'sort_order': 7},
    {'code': 'JZ', 'name': '精整车间', 'sort_order': 8},
    {'code': 'JZ2', 'name': '二分厂精整车间', 'sort_order': 9},
    {'code': 'JQ', 'name': '园区剪切车间', 'sort_order': 10},
    {'code': 'CPK', 'name': '成品库', 'sort_order': 11},
]

EQUIPMENT_BY_WORKSHOP = {
    'ZD': [
        {'code': 'ZD-1', 'name': '1#线', 'machine_type': 'ingot_caster', 'shift_mode': 'three', 'operational_status': 'running'},
        {'code': 'ZD-2', 'name': '2#线', 'machine_type': 'ingot_caster', 'shift_mode': 'three', 'operational_status': 'running'},
        {'code': 'ZD-3', 'name': '3#线', 'machine_type': 'ingot_caster', 'shift_mode': 'three', 'operational_status': 'stopped'},
        {'code': 'ZD-4', 'name': '4#线', 'machine_type': 'ingot_caster', 'shift_mode': 'three', 'operational_status': 'stopped'},
    ],
    'ZR2': [
        {
            'code': 'ZR2-1',
            'name': '1#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'running',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        },
        {
            'code': 'ZR2-2',
            'name': '2#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'running',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        },
        {
            'code': 'ZR2-3',
            'name': '3#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'stopped',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        },
        {
            'code': 'ZR2-4',
            'name': '4#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'stopped',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        },
        {
            'code': 'ZR2-5',
            'name': '5#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'running',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        },
        {
            'code': 'ZR2-6',
            'name': '6#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'running',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        },
    ],
    'ZR3': [
        {'code': 'ZR3-1', 'name': '1#机', 'machine_type': 'cast_roller', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'RZ': [
        {
            'code': 'RZ-ZJ',
            'name': '轧机',
            'machine_type': 'hot_mill',
            'shift_mode': 'three',
            'operational_status': 'running',
            'custom_fields': HOT_ROLL_CUSTOM_FIELDS,
        },
        {
            'code': 'RZ-XC',
            'name': '铣床',
            'machine_type': 'milling',
            'shift_mode': 'two',
            'assigned_shift_ids': [1, 2],
            'operational_status': 'running',
        },
        {
            'code': 'RZ-JC',
            'name': '锯床',
            'machine_type': 'sawing',
            'shift_mode': 'two',
            'assigned_shift_ids': [1, 2],
            'operational_status': 'running',
        },
    ],
    'LZ2050': [
        {'code': 'LZ2050-1', 'name': '2050轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'LZ1450': [
        {'code': 'LZ1450-1', 'name': '1450轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'JZ': [
        {'code': 'JZ-LWJ1', 'name': '拉弯矫1#', 'machine_type': 'straightener'},
        {'code': 'JZ-LWJ2', 'name': '拉弯矫2#', 'machine_type': 'straightener'},
        {'code': 'JZ-LWJ3', 'name': '拉弯矫3#', 'machine_type': 'straightener'},
        {'code': 'JZ-HJ1', 'name': '横剪1#', 'machine_type': 'cross_cut'},
        {'code': 'JZ-HJ2', 'name': '横剪2#', 'machine_type': 'cross_cut'},
        {'code': 'JZ-HJ3', 'name': '横剪3#', 'machine_type': 'cross_cut'},
        {'code': 'JZ-ZJ1', 'name': '纵剪1#', 'machine_type': 'slitter'},
        {'code': 'JZ-ZJ2', 'name': '纵剪2#', 'machine_type': 'slitter'},
        {'code': 'JZ-ZJ3', 'name': '纵剪3#', 'machine_type': 'slitter'},
        {'code': 'JZ-FT1', 'name': '分条1#', 'machine_type': 'slitter'},
        {'code': 'JZ-FJ', 'name': '飞剪', 'machine_type': 'fly_cut'},
    ],
    'JZ2': [
        {'code': 'JZ2-1', 'name': '1#', 'machine_type': 'finishing'},
        {'code': 'JZ2-2', 'name': '2#', 'machine_type': 'finishing'},
        {'code': 'JZ2-3', 'name': '3#', 'machine_type': 'finishing'},
        {'code': 'JZ2-4', 'name': '4#', 'machine_type': 'finishing'},
        {'code': 'JZ2-5', 'name': '5#', 'machine_type': 'finishing'},
        {'code': 'JZ2-6', 'name': '6#', 'machine_type': 'finishing'},
        {'code': 'JZ2-7', 'name': '7#', 'machine_type': 'finishing'},
        {'code': 'JZ2-8', 'name': '8#', 'machine_type': 'finishing'},
    ],
    'JQ': [
        {'code': 'JQ-1', 'name': '1#', 'machine_type': 'shear'},
        {'code': 'JQ-2', 'name': '2#', 'machine_type': 'shear'},
        {'code': 'JQ-3', 'name': '3#', 'machine_type': 'shear'},
        {'code': 'JQ-4', 'name': '4#', 'machine_type': 'shear'},
        {'code': 'JQ-ZJ', 'name': '重卷', 'machine_type': 'recoiler'},
    ],
}

SHIFT_TEAMS = [
    ('A', '白班组', 1),
    ('B', '小夜班组', 2),
    ('C', '大夜班组', 3),
]

PRODUCTION_OWNER_ACCOUNTS = [
    ('EN', '电工班长', 'energy_stat'),
    ('MT', '机修班长', 'maintenance_lead'),
    ('HY', '液压班长', 'hydraulic_lead'),
    ('QC', '质检责任人', 'qc'),
    ('PLAN', '合同责任人', 'contracts'),
]

WAREHOUSE_OWNER_ACCOUNTS = [
    ('INV', '成品库负责人', 'inventory_keeper'),
    ('PLAN', '计划科负责人', 'contracts'),
    ('UTILITY', '水电气负责人', 'utility_manager'),
]

E2E_OWNER_PIN_BY_USERNAME = {
    'CPK-A-INV': '506371',
    'CPK-A-PLAN': '101901',
    'CPK-A-UTILITY': '591767',
}

REAL_WORKSHOP_CODES = {item['code'] for item in WORKSHOPS}
REAL_TEAM_CODES = {f"{item['code']}-{shift_code}" for item in WORKSHOPS for shift_code, _name, _sort_order in SHIFT_TEAMS}
REAL_EQUIPMENT_CODES = {
    row['code']
    for equipment_rows in EQUIPMENT_BY_WORKSHOP.values()
    for row in equipment_rows
}


def _is_placeholder_text(value: str | None) -> bool:
    return bool(value and '?' in value)


def _deactivate_placeholder_rows(db: Session, model) -> None:
    rows = db.execute(select(model)).scalars().all()
    for item in rows:
        if _is_placeholder_text(getattr(item, 'name', None)) or _is_placeholder_text(getattr(item, 'code', None)):
            item.is_active = False


def _deactivate_legacy_rows(db: Session) -> None:
    inactive_workshop_ids: set[int] = set()

    workshops = db.execute(select(Workshop)).scalars().all()
    for item in workshops:
        if item.code not in REAL_WORKSHOP_CODES:
            item.is_active = False
            inactive_workshop_ids.add(item.id)

    teams = db.execute(select(Team)).scalars().all()
    for item in teams:
        if item.code not in REAL_TEAM_CODES or item.workshop_id in inactive_workshop_ids:
            item.is_active = False

    equipment_rows = db.execute(select(Equipment)).scalars().all()
    for item in equipment_rows:
        if item.code not in REAL_EQUIPMENT_CODES or item.workshop_id in inactive_workshop_ids:
            item.is_active = False


def seed_real_workshops(db: Session) -> dict[str, Workshop]:
    existing = {item.code: item for item in db.execute(select(Workshop)).scalars().all()}
    for payload in WORKSHOPS:
        item = existing.get(payload['code'])
        workshop_type = WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(payload['code'])
        if item is None:
            item = Workshop(
                code=payload['code'],
                name=payload['name'],
                workshop_type=workshop_type,
                sort_order=payload['sort_order'],
                is_active=True,
            )
            db.add(item)
            existing[payload['code']] = item
            continue

        item.name = payload['name']
        item.workshop_type = workshop_type
        item.sort_order = payload['sort_order']
        item.is_active = True

    db.flush()
    return existing


def seed_real_teams(db: Session, workshops_by_code: dict[str, Workshop]) -> None:
    existing = {item.code: item for item in db.execute(select(Team)).scalars().all()}
    for workshop in WORKSHOPS:
        workshop_id = workshops_by_code[workshop['code']].id
        for shift_code, team_name, sort_order in SHIFT_TEAMS:
            team_code = f"{workshop['code']}-{shift_code}"
            item = existing.get(team_code)
            if item is None:
                item = Team(
                    code=team_code,
                    name=team_name,
                    workshop_id=workshop_id,
                    sort_order=sort_order,
                    is_active=True,
                )
                db.add(item)
                existing[team_code] = item
                continue

            item.name = team_name
            item.workshop_id = workshop_id
            item.sort_order = sort_order
            item.is_active = True


def _equipment_payload(payload: dict, workshop_id: int) -> dict:
    shift_mode = payload.get('shift_mode', 'three')
    assigned_shift_ids = payload.get('assigned_shift_ids')
    return {
        'code': payload['code'],
        'name': payload['name'],
        'workshop_id': workshop_id,
        'equipment_type': payload['machine_type'],
        'operational_status': payload.get('operational_status', 'running'),
        'shift_mode': shift_mode,
        'assigned_shift_ids': assigned_shift_ids,
        'custom_fields': payload.get('custom_fields'),
        'qr_code': f"XT-{payload['code']}",
        'sort_order': payload.get('sort_order', 0),
        'is_active': True,
    }


def _default_shift_ids(shift_mode: str) -> list[int]:
    return [1, 2, 3] if shift_mode == 'three' else [1, 2]


def _team_shift_code(team_code: str | None) -> str | None:
    if not team_code:
        return None
    parts = str(team_code).split('-')
    if len(parts) < 2:
        return None
    return parts[-1].strip().upper() or None


def _ensure_machine_account_binding(db: Session, *, equipment: Equipment, workshop: Workshop) -> None:
    shift_mode = (equipment.shift_mode or 'three').strip().lower()
    if shift_mode not in {'two', 'three'}:
        shift_mode = 'three'
    equipment.shift_mode = shift_mode
    equipment.assigned_shift_ids = list(equipment.assigned_shift_ids or _default_shift_ids(shift_mode))
    equipment.qr_code = f"XT-{equipment.code}"

    user: User | None = db.get(User, equipment.bound_user_id) if equipment.bound_user_id else None
    username_user = db.execute(select(User).where(User.username == equipment.code)).scalar_one_or_none()
    if username_user is not None:
        user = username_user

    if user is None:
        pin = generate_random_pin(6)
        user = User(
            username=equipment.code,
            password_hash=get_password_hash(pin),
            pin_code=pin,
            name=f"{workshop.name} {equipment.name}",
            role='shift_leader',
            workshop_id=workshop.id,
            team_id=None,
            data_scope_type='self_workshop',
            assigned_shift_ids=equipment.assigned_shift_ids,
            is_mobile_user=True,
            is_reviewer=False,
            is_manager=False,
            is_active=equipment.operational_status == 'running',
        )
        db.add(user)
        db.flush()
    else:
        user.username = equipment.code
        user.name = f"{workshop.name} {equipment.name}"
        user.role = 'shift_leader'
        user.workshop_id = workshop.id
        user.team_id = None
        user.data_scope_type = 'self_workshop'
        user.assigned_shift_ids = equipment.assigned_shift_ids
        user.is_mobile_user = True
        user.is_reviewer = False
        user.is_manager = False
        user.is_active = equipment.operational_status == 'running'
        if not user.pin_code:
            user.pin_code = generate_random_pin(6)
        if not user.password_hash or not verify_password(user.pin_code, user.password_hash):
            user.password_hash = get_password_hash(user.pin_code)

    equipment.bound_user_id = user.id


def seed_real_equipment(db: Session, workshops_by_code: dict[str, Workshop]) -> None:
    existing = {item.code: item for item in db.execute(select(Equipment)).scalars().all()}

    for workshop_code, equipment_rows in EQUIPMENT_BY_WORKSHOP.items():
        workshop = workshops_by_code[workshop_code]
        workshop_id = workshop.id
        for sort_order, payload in enumerate(equipment_rows, start=1):
            normalized = _equipment_payload({**payload, 'sort_order': sort_order}, workshop_id)
            item = existing.get(payload['code'])
            if item is None:
                item = Equipment(**normalized)
                db.add(item)
                existing[payload['code']] = item
                continue

            item.name = normalized['name']
            item.workshop_id = normalized['workshop_id']
            item.equipment_type = normalized['equipment_type']
            item.operational_status = normalized['operational_status']
            item.shift_mode = normalized['shift_mode']
            item.assigned_shift_ids = normalized['assigned_shift_ids']
            item.custom_fields = normalized['custom_fields']
            item.qr_code = normalized['qr_code']
            item.sort_order = normalized['sort_order']
            item.is_active = True

        for payload in equipment_rows:
            item = existing[payload['code']]
            _ensure_machine_account_binding(db, equipment=item, workshop=workshop)


def _owner_templates_for_workshop(workshop_code: str) -> list[tuple[str, str, str]]:
    if workshop_code == 'CPK':
        return WAREHOUSE_OWNER_ACCOUNTS
    return PRODUCTION_OWNER_ACCOUNTS


def _ensure_special_owner_account(
    db: Session,
    *,
    workshop: Workshop,
    team: Team,
    shift_id: int | None,
    username: str,
    role_label: str,
    role_code: str,
) -> None:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    assigned_shift_ids = [shift_id] if shift_id is not None else []
    stable_pin = E2E_OWNER_PIN_BY_USERNAME.get(username)

    if user is None:
        pin = stable_pin or generate_random_pin(6)
        user = User(
            username=username,
            password_hash=get_password_hash(pin),
            pin_code=pin,
            name=f'{workshop.name}{team.name}{role_label}',
            role=role_code,
            workshop_id=workshop.id,
            team_id=team.id,
            data_scope_type='self_workshop',
            assigned_shift_ids=assigned_shift_ids,
            is_mobile_user=True,
            is_reviewer=False,
            is_manager=False,
            is_active=True,
        )
        db.add(user)
        return

    user.name = f'{workshop.name}{team.name}{role_label}'
    user.role = role_code
    user.workshop_id = workshop.id
    user.team_id = team.id
    user.data_scope_type = 'self_workshop'
    user.assigned_shift_ids = assigned_shift_ids
    user.is_mobile_user = True
    user.is_reviewer = False
    user.is_manager = False
    user.is_active = True
    if stable_pin:
        user.pin_code = stable_pin
    if not user.pin_code:
        user.pin_code = generate_random_pin(6)
    if not user.password_hash or not verify_password(user.pin_code, user.password_hash):
        user.password_hash = get_password_hash(user.pin_code)


def seed_special_owner_users(db: Session, workshops_by_code: dict[str, Workshop]) -> None:
    shifts_by_code = {
        str(item.code).strip().upper(): item.id
        for item in db.execute(select(ShiftConfig).where(ShiftConfig.is_active.is_(True))).scalars().all()
    }
    teams = db.execute(select(Team).where(Team.is_active.is_(True))).scalars().all()
    teams_by_workshop: dict[int, list[Team]] = {}
    for item in teams:
        teams_by_workshop.setdefault(item.workshop_id, []).append(item)

    for rows in teams_by_workshop.values():
        rows.sort(key=lambda item: (item.sort_order, item.id))

    for workshop_code, workshop in workshops_by_code.items():
        owner_templates = _owner_templates_for_workshop(workshop_code)
        for team in teams_by_workshop.get(workshop.id, []):
            shift_code = _team_shift_code(team.code)
            shift_id = shifts_by_code.get(shift_code or '')
            for username_suffix, role_label, role_code in owner_templates:
                username = f'{workshop_code}-{shift_code or "A"}-{username_suffix}'
                _ensure_special_owner_account(
                    db,
                    workshop=workshop,
                    team=team,
                    shift_id=shift_id,
                    username=username,
                    role_label=role_label,
                    role_code=role_code,
                )


def seed_real_master_data(db: Session) -> None:
    _deactivate_placeholder_rows(db, Workshop)
    _deactivate_placeholder_rows(db, Team)
    _deactivate_placeholder_rows(db, Equipment)
    _deactivate_legacy_rows(db)

    workshops_by_code = seed_real_workshops(db)
    seed_real_teams(db, workshops_by_code)
    seed_real_equipment(db, workshops_by_code)
    seed_special_owner_users(db, workshops_by_code)

    db.commit()
