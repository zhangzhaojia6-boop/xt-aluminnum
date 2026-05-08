from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_password_hash, verify_password
from app.core.workshop_templates import WORKSHOP_TYPE_BY_WORKSHOP_CODE
from app.models.master import Equipment, MasterCodeAlias, Team, Workshop
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
    {'code': 'ZR5', 'name': '铸五车间', 'sort_order': 4},
    {'code': 'ZR6', 'name': '铸六车间', 'sort_order': 5},
    {'code': 'RZ', 'name': '热轧车间', 'sort_order': 6},
    {'code': 'LZ2050', 'name': '2050冷轧车间', 'sort_order': 7},
    {'code': 'LZ1850', 'name': '1850冷轧车间', 'sort_order': 8},
    {'code': 'LZ1650', 'name': '1650冷轧车间', 'sort_order': 9},
    {'code': 'LZ1450', 'name': '1450冷轧车间', 'sort_order': 10},
    {'code': 'LZ3', 'name': '冷轧三车间', 'sort_order': 11},
    {'code': 'HWB', 'name': '花纹板车间', 'sort_order': 12},
    {'code': 'JZ', 'name': '精整车间', 'sort_order': 13},
    {'code': 'JZ2', 'name': '二分厂精整车间', 'sort_order': 14},
    {'code': 'JQ', 'name': '园区剪切车间', 'sort_order': 15},
    {'code': 'CT', 'name': '彩涂车间', 'sort_order': 16},
    {'code': 'HS', 'name': '回收车间', 'sort_order': 17},
    {'code': 'CPK', 'name': '成品库', 'sort_order': 18},
    {'code': 'ZXTF', 'name': '在线退火车间', 'sort_order': 200},
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
        {
            'code': f'ZR3-{index}',
            'name': f'{index}#机',
            'machine_type': 'cast_roller',
            'shift_mode': 'three',
            'operational_status': 'running',
            'custom_fields': ZR2_CUSTOM_FIELDS,
        }
        for index in range(1, 10)
    ],
    'ZR5': [
        {'code': 'ZR5-1', 'name': '1#机', 'machine_type': 'cast_roller', 'shift_mode': 'three', 'operational_status': 'running', 'custom_fields': ZR2_CUSTOM_FIELDS},
    ],
    'ZR6': [
        {'code': 'ZR6-1', 'name': '1#机', 'machine_type': 'cast_roller', 'shift_mode': 'three', 'operational_status': 'running', 'custom_fields': ZR2_CUSTOM_FIELDS},
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
    'LZ1850': [
        {'code': 'LZ1850-1', 'name': '1850轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'LZ1650': [
        {'code': 'LZ1650-1', 'name': '1650轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'LZ1450': [
        {'code': 'LZ1450-1', 'name': '1450轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'HWB': [
        {'code': 'HWB-1', 'name': '花纹板主轧', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'},
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
    'ZXTF': [
        {'code': 'ZXTF-1', 'name': '1#线', 'machine_type': 'annealing_line', 'shift_mode': 'three', 'operational_status': 'running'},
        {'code': 'ZXTF-2', 'name': '2#线', 'machine_type': 'annealing_line', 'shift_mode': 'three', 'operational_status': 'running'},
        {'code': 'ZXTF-3', 'name': '3#线', 'machine_type': 'annealing_line', 'shift_mode': 'three', 'operational_status': 'running'},
        {'code': 'ZXTF-4', 'name': '4#线', 'machine_type': 'annealing_line', 'shift_mode': 'three', 'operational_status': 'running'},
    ],
    'CT': [
        {'code': 'CT-XY', 'name': '洗油拉矫退火线', 'machine_type': 'coating_line', 'shift_mode': 'two', 'operational_status': 'running'},
        {'code': 'CT-TQ', 'name': '涂漆线', 'machine_type': 'coating_line', 'shift_mode': 'two', 'operational_status': 'running'},
    ],
    'HS': [
        {'code': 'HS-1', 'name': '回收1#', 'machine_type': 'recycling', 'shift_mode': 'two', 'operational_status': 'running'},
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
VIRTUAL_QR_EQUIPMENT_TYPES = {'virtual_role_qr', 'virtual_workshop_qr'}
ROLE_QR_SUFFIX_MAP = {
    'OP': ('machine_operator', '主操'),
    'EN': ('energy_stat', '电工'),
    'HY': ('hydraulic_lead', '液压'),
    'MT': ('maintenance_lead', '机修'),
}

MES_WORKSHOP_ALIASES = [
    ('LZ2050', '2050车间'),
    ('LZ2050', '冷轧2050车间'),
    ('LZ1850', '1850车间'),
    ('LZ1850', '冷轧1850车间'),
    ('LZ1850', '1850冷轧'),
    ('LZ1650', '1650车间'),
    ('LZ1650', '冷轧1650车间'),
    ('LZ1650', '1650冷轧'),
    ('LZ1450', '1450车间'),
    ('LZ1450', '冷轧1450车间'),
    ('HWB', '花纹板'),
    ('HWB', '花纹板车间'),
    ('HWB', '花纹板冷轧'),
    ('RZ', '热轧'),
    ('RZ', '热轧车间'),
    ('JZ', '精整'),
    ('JZ', '精整车间'),
    ('JZ', '拉矫'),
    ('JZ', '拉矫车间'),
    ('JQ', '园区精整'),
    ('JQ', '园区剪切'),
    ('JQ', '园区剪切车间'),
    ('JQ', '园区淬火'),
    ('JQ', '园区淬火车间'),
    ('CT', '彩涂'),
    ('CT', '彩涂车间'),
    ('HS', '回收'),
    ('HS', '回收车间'),
    ('ZR5', '铸五'),
    ('ZR5', '铸五车间'),
    ('ZR6', '铸六'),
    ('ZR6', '铸六车间'),
    ('ZXTF', '新厂在线车间'),
    ('ZXTF', '园区在线车间'),
    ('ZXTF', '在线退火'),
    ('ZXTF', '在线退火车间'),
]

PROCESS_BUSINESS_UNITS = [
    {'unit_code': 'casting_branch', 'unit_name': '铸轧分厂', 'workshop_codes': ['ZD', 'ZR2', 'ZR3', 'ZR5', 'ZR6']},
    {'unit_code': 'rolling_branch', 'unit_name': '轧制分厂', 'workshop_codes': ['RZ', 'LZ2050', 'LZ1850', 'LZ1650', 'LZ1450', 'LZ3', 'HWB']},
    {'unit_code': 'finishing_branch', 'unit_name': '精整分厂', 'workshop_codes': ['JZ']},
    {'unit_code': 'second_branch', 'unit_name': '二分厂', 'workshop_codes': ['JZ2']},
    {'unit_code': 'park_area', 'unit_name': '园区', 'workshop_codes': ['JQ']},
    {'unit_code': 'coating_branch', 'unit_name': '彩涂车间', 'workshop_codes': ['CT']},
    {'unit_code': 'recycling_branch', 'unit_name': '回收车间', 'workshop_codes': ['HS']},
    {'unit_code': 'warehouse_logistics', 'unit_name': '成品库与发运', 'workshop_codes': ['CPK']},
    {'unit_code': 'online_annealing', 'unit_name': '在线退火跨厂区', 'workshop_codes': ['ZXTF']},
]

WORKSHOP_PROCESS_BUSINESS = {
    'ZD': {
        'process_business': '铸锭/熔炼前段',
        'process_tags': ['熔炼', '铸锭'],
        'area_status': 'confirmed',
    },
    'ZR2': {
        'process_business': '铸轧',
        'process_tags': ['铸轧', '卷坯'],
        'area_status': 'confirmed',
    },
    'ZR3': {
        'process_business': '铸轧',
        'process_tags': ['铸轧', '卷坯'],
        'area_status': 'confirmed',
    },
    'RZ': {
        'process_business': '热轧',
        'process_tags': ['热轧', '铣面', '锯切'],
        'area_status': 'confirmed',
    },
    'LZ2050': {
        'process_business': '2050冷轧',
        'process_tags': ['冷轧', '2050'],
        'area_status': 'confirmed',
    },
    'LZ1850': {
        'process_business': '1850冷轧',
        'process_tags': ['冷轧', '1850'],
        'area_status': 'confirmed',
    },
    'LZ1650': {
        'process_business': '1650冷轧',
        'process_tags': ['冷轧', '1650'],
        'area_status': 'confirmed',
    },
    'LZ1450': {
        'process_business': '1450冷轧',
        'process_tags': ['冷轧', '1450'],
        'area_status': 'confirmed',
    },
    'LZ3': {
        'process_business': '冷轧三车间',
        'process_tags': ['冷轧'],
        'area_status': 'needs_machine_line_confirmation',
    },
    'HWB': {
        'process_business': '花纹板冷轧',
        'process_tags': ['冷轧', '花纹板'],
        'area_status': 'confirmed',
    },
    'JZ': {
        'process_business': '精整/拉矫/剪切',
        'process_tags': ['拉弯矫', '横剪', '纵剪', '分条', '飞剪'],
        'area_status': 'confirmed',
    },
    'JZ2': {
        'process_business': '二分厂精整',
        'process_tags': ['精整'],
        'area_status': 'needs_machine_process_confirmation',
    },
    'JQ': {
        'process_business': '园区剪切/重卷',
        'process_tags': ['剪切', '重卷'],
        'area_status': 'confirmed',
    },
    'CPK': {
        'process_business': '成品库存/入库/发货',
        'process_tags': ['成品库', '入库', '发货', '库存'],
        'area_status': 'confirmed',
    },
    'ZXTF': {
        'process_business': '在线退火',
        'process_tags': ['新厂在线', '园区在线', '在线退火'],
        'area_status': 'needs_mes_line_split',
    },
    'ZR5': {
        'process_business': '铸轧',
        'process_tags': ['铸轧', '卷坯'],
        'area_status': 'confirmed',
    },
    'ZR6': {
        'process_business': '铸轧',
        'process_tags': ['铸轧', '卷坯'],
        'area_status': 'confirmed',
    },
    'CT': {
        'process_business': '彩涂',
        'process_tags': ['彩涂', '涂漆', '洗油'],
        'area_status': 'confirmed',
    },
    'HS': {
        'process_business': '回收',
        'process_tags': ['回收', '废料回收'],
        'area_status': 'confirmed',
    },
}

MACHINE_PROCESS_BUSINESS_BY_CODE = {
    'RZ-ZJ': '热轧轧制',
    'RZ-XC': '铣面',
    'RZ-JC': '锯切',
    'LZ2050-1': '2050冷轧',
    'LZ1850-1': '1850冷轧',
    'LZ1650-1': '1650冷轧',
    'LZ1450-1': '1450冷轧',
    'HWB-1': '花纹板冷轧',
    'JZ-LWJ1': '拉弯矫/洗拉',
    'JZ-LWJ2': '拉弯矫/洗拉',
    'JZ-LWJ3': '拉弯矫/洗拉',
    'JZ-HJ1': '横剪/剪切',
    'JZ-HJ2': '横剪/剪切',
    'JZ-HJ3': '横剪/剪切',
    'JZ-ZJ1': '纵剪',
    'JZ-ZJ2': '纵剪',
    'JZ-ZJ3': '纵剪',
    'JZ-FT1': '分条',
    'JZ-FJ': '飞剪',
    'JQ-ZJ': '重卷',
    'CT-XY': '彩涂/洗油退火',
    'CT-TQ': '彩涂/涂漆',
    'HS-1': '回收',
}

MACHINE_PROCESS_BUSINESS_BY_TYPE = {
    'ingot_caster': '铸锭',
    'cast_roller': '铸轧',
    'cold_mill': '冷轧',
    'finishing': '精整',
    'shear': '剪切',
    'annealing_line': '在线退火',
    'coating_line': '彩涂',
    'recycling': '回收',
}


def build_process_business_hierarchy() -> dict:
    workshops = {item['code']: item for item in WORKSHOPS}
    mes_aliases: dict[str, list[str]] = {}
    for canonical_code, alias_text in MES_WORKSHOP_ALIASES:
        mes_aliases.setdefault(canonical_code, []).append(alias_text)

    units = []
    for unit in PROCESS_BUSINESS_UNITS:
        workshop_rows = []
        for workshop_code in unit['workshop_codes']:
            workshop = workshops[workshop_code]
            process_business = WORKSHOP_PROCESS_BUSINESS[workshop_code]
            machines = []
            for machine in EQUIPMENT_BY_WORKSHOP.get(workshop_code, []):
                machine_code = machine['code']
                machines.append(
                    {
                        'machine_code': machine_code,
                        'machine_name': machine['name'],
                        'machine_type': machine['machine_type'],
                        'process_business': MACHINE_PROCESS_BUSINESS_BY_CODE.get(
                            machine_code,
                            MACHINE_PROCESS_BUSINESS_BY_TYPE.get(machine['machine_type'], ''),
                        ),
                        'shift_mode': machine.get('shift_mode', 'three'),
                        'operational_status': machine.get('operational_status', 'running'),
                    }
                )
            workshop_rows.append(
                {
                    'workshop_code': workshop_code,
                    'workshop_name': workshop['name'],
                    'workshop_type': WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(workshop_code),
                    'process_business': process_business['process_business'],
                    'process_tags': list(process_business['process_tags']),
                    'area_status': process_business['area_status'],
                    'mes_aliases': mes_aliases.get(workshop_code, []),
                    'machines': machines,
                }
            )
        units.append(
            {
                'unit_code': unit['unit_code'],
                'unit_name': unit['unit_name'],
                'workshops': workshop_rows,
            }
        )

    return {
        'source': 'real_master_data',
        'status': 'workshop_machine_process_business_map',
        'units': units,
        'open_items': [
            '新厂在线车间和园区在线车间当前映射到ZXTF，仍需MES设备/南北线字段拆分',
            'JZ2二分厂精整当前只有1#到8#机列，具体横剪/纵剪/拉矫职责需要现场确认',
        ],
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
    virtual_qr_workshop_ids = {
        item
        for item in db.execute(
            select(Equipment.workshop_id).where(Equipment.equipment_type.in_(VIRTUAL_QR_EQUIPMENT_TYPES))
        ).scalars()
        if item is not None
    }

    workshops = db.execute(select(Workshop)).scalars().all()
    for item in workshops:
        if item.id in virtual_qr_workshop_ids:
            item.is_active = True
            continue
        if item.code not in REAL_WORKSHOP_CODES:
            item.is_active = False
            inactive_workshop_ids.add(item.id)

    teams = db.execute(select(Team)).scalars().all()
    for item in teams:
        if item.code not in REAL_TEAM_CODES or item.workshop_id in inactive_workshop_ids:
            item.is_active = False

    equipment_rows = db.execute(select(Equipment)).scalars().all()
    for item in equipment_rows:
        if item.equipment_type in VIRTUAL_QR_EQUIPMENT_TYPES:
            continue
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


def _keep_existing_qr_code(current: str | None, generated: str) -> str:
    return str(current or '').strip() or generated


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
    equipment.qr_code = _keep_existing_qr_code(equipment.qr_code, f"XT-{equipment.code}")

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
            item.qr_code = _keep_existing_qr_code(item.qr_code, normalized['qr_code'])
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


def seed_virtual_role_qr_accounts(db: Session) -> None:
    rows = (
        db.execute(
            select(Equipment)
            .where(Equipment.equipment_type == 'virtual_role_qr')
            .order_by(Equipment.workshop_id.asc(), Equipment.sort_order.asc(), Equipment.id.asc())
        )
        .scalars()
        .all()
    )
    for equipment in rows:
        workshop = db.get(Workshop, equipment.workshop_id)
        if workshop is None:
            equipment.is_active = False
            continue
        if not workshop.is_active:
            workshop.is_active = True

        qr_suffix = (equipment.code or '').rsplit('-', 1)[-1].upper()
        mapping = ROLE_QR_SUFFIX_MAP.get(qr_suffix)
        if mapping is None:
            equipment.is_active = False
            continue

        system_role, role_label = mapping
        username = equipment.code.upper()
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                password_hash=get_password_hash(secrets.token_urlsafe(24)),
                name=equipment.name or f'{workshop.name}{role_label}',
                role=system_role,
                workshop_id=workshop.id,
                team_id=None,
                data_scope_type='self_workshop',
                assigned_shift_ids=[],
                is_mobile_user=True,
                is_reviewer=False,
                is_manager=False,
                is_active=True,
            )
            db.add(user)
            db.flush()
        else:
            user.name = equipment.name or f'{workshop.name}{role_label}'
            user.role = system_role
            user.workshop_id = workshop.id
            user.team_id = None
            user.data_scope_type = 'self_workshop'
            user.assigned_shift_ids = list(user.assigned_shift_ids or [])
            user.is_mobile_user = True
            user.is_reviewer = False
            user.is_manager = False
            user.is_active = True
            if not user.password_hash:
                user.password_hash = get_password_hash(secrets.token_urlsafe(24))

        equipment.operational_status = 'running'
        equipment.bound_user_id = user.id
        equipment.is_active = True


def seed_mes_master_aliases(db: Session) -> None:
    existing = {
        (item.entity_type, item.alias_code, item.source_type): item
        for item in db.execute(select(MasterCodeAlias)).scalars().all()
    }
    for canonical_code, alias_text in MES_WORKSHOP_ALIASES:
        key = ('workshop', alias_text, 'mes_mvc')
        item = existing.get(key)
        if item is None:
            item = MasterCodeAlias(
                entity_type='workshop',
                canonical_code=canonical_code,
                alias_code=alias_text,
                alias_name=alias_text,
                source_type='mes_mvc',
                is_active=True,
            )
            db.add(item)
            existing[key] = item
            continue

        item.canonical_code = canonical_code
        item.alias_name = alias_text
        item.is_active = True


def seed_real_master_data(db: Session) -> None:
    _deactivate_placeholder_rows(db, Workshop)
    _deactivate_placeholder_rows(db, Team)
    _deactivate_placeholder_rows(db, Equipment)
    _deactivate_legacy_rows(db)

    workshops_by_code = seed_real_workshops(db)
    seed_real_teams(db, workshops_by_code)
    seed_real_equipment(db, workshops_by_code)
    seed_mes_master_aliases(db)
    seed_special_owner_users(db, workshops_by_code)
    seed_virtual_role_qr_accounts(db)

    db.commit()
