from __future__ import annotations

from copy import deepcopy
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.field_permissions import READ_ALL, check_field_write, get_readable_fields, normalize_role
from app.models.master import WorkshopTemplateConfig


WORK_ORDER_FIELD_NAMES = {'alloy_grade', 'contract_no', 'customer_name', 'contract_weight'}

WORK_ORDER_ENTRY_FIELD_NAMES = {
    'machine_id',
    'shift_id',
    'business_date',
    'entry_type',
    'on_machine_time',
    'off_machine_time',
    'input_weight',
    'output_weight',
    'input_spec',
    'output_spec',
    'material_state',
    'scrap_weight',
    'spool_weight',
    'operator_notes',
    'verified_input_weight',
    'verified_output_weight',
    'qc_grade',
    'qc_notes',
    'energy_kwh',
    'gas_m3',
    'yield_rate',
}

NUMERIC_FIELD_NAMES = {
    'input_weight',
    'output_weight',
    'scrap_weight',
    'spool_weight',
    'energy_kwh',
    'gas_m3',
    'verified_input_weight',
    'verified_output_weight',
    'cast_speed',
    'paper_furnace',
    'static_furnace',
    'unit_output',
    'gas_consumption',
    'skin_weight',
    'trim_weight',
    'tray_weight',
    'roll_speed',
}

TIME_FIELD_NAMES = {'on_machine_time', 'off_machine_time'}

WORKSHOP_TYPE_BY_WORKSHOP_CODE: dict[str, str | None] = {
    'ZD': 'casting',
    'ZR2': 'casting',
    'ZR3': 'casting',
    'RZ': 'hot_roll',
    'LZ2050': 'cold_roll',
    'LZ1450': 'cold_roll',
    'LZ3': 'cold_roll',
    'JZ': 'finishing',
    'JZ2': 'finishing',
    'JQ': 'shearing',
    'CPK': 'inventory',
    'ZXTF': 'annealing',
}

WORKSHOP_TYPE_ALIASES = {
    'cold_roll': 'cold_roll',
    'cold_rolling_2050': 'cold_roll',
    'cold_rolling_1450': 'cold_roll',
    'hot_roll': 'hot_roll',
    'hot_rolling': 'hot_roll',
    'finishing': 'finishing',
    'shearing': 'shearing',
    'cutting': 'shearing',
    'casting': 'casting',
    'inventory': 'inventory',
    'warehouse': 'inventory',
    'annealing': 'annealing',
}

ENERGY_OWNER_FIELDS = [
    {
        'name': 'energy_kwh',
        'label': '电耗',
        'type': 'number',
        'unit': 'kWh',
        'required': True,
        'role_write': ['energy_stat'],
        'role_read': ['energy_stat', 'admin', 'manager'],
        'hint': '由电工班长或能耗责任人补录。',
    },
    {
        'name': 'gas_m3',
        'label': '气耗',
        'type': 'number',
        'unit': 'm³',
        'required': False,
        'role_write': ['energy_stat'],
        'role_read': ['energy_stat', 'admin', 'manager'],
        'hint': '由电工班长或能耗责任人补录。',
    },
]

MAINTENANCE_OWNER_FIELDS = [
    {
        'name': 'downtime_minutes',
        'label': '停机分钟',
        'type': 'number',
        'unit': 'min',
        'required': False,
        'role_write': ['maintenance_lead'],
        'role_read': ['maintenance_lead', 'admin', 'manager'],
        'hint': '由机修班长补录设备停机时长。',
    },
    {
        'name': 'downtime_reason',
        'label': '停机原因',
        'type': 'text',
        'required': False,
        'role_write': ['maintenance_lead'],
        'role_read': ['maintenance_lead', 'admin', 'manager'],
        'hint': '由机修班长补录设备状态说明。',
    },
]

HYDRAULIC_OWNER_FIELDS = [
    {
        'name': 'hydraulic_oil_32',
        'label': '32#液压油',
        'type': 'number',
        'unit': '桶',
        'required': False,
        'role_write': ['hydraulic_lead'],
        'role_read': ['hydraulic_lead', 'admin', 'manager'],
        'hint': '由液压班长补录当班耗材。',
    },
    {
        'name': 'hydraulic_oil_46',
        'label': '46#液压油',
        'type': 'number',
        'unit': '桶',
        'required': False,
        'role_write': ['hydraulic_lead'],
        'role_read': ['hydraulic_lead', 'admin', 'manager'],
        'hint': '由液压班长补录当班耗材。',
    },
]

CONSUMABLE_OWNER_FIELDS = {
    'casting': [
        {'name': 'liquefied_gas_per_ton', 'label': '液化气吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'titanium_wire_per_ton', 'label': '钛丝吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'steel_strip_per_ton', 'label': '钢带吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'magnesium_per_ton', 'label': '镁锭吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'manganese_per_ton', 'label': '锰剂吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'iron_per_ton', 'label': '铁剂吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'copper_per_ton', 'label': '铜剂吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
    ],
    'hot_roll': [
        {'name': 'hot_roll_emulsion_per_ton', 'label': '热轧乳液吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
    ],
    'cold_roll': [
        {'name': 'rolling_oil_per_ton', 'label': '轧制油吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'filter_agent_per_ton', 'label': '飞滤剂吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'diatomite_per_ton', 'label': '硅藻土吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'white_earth_per_ton', 'label': '白土吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'filter_cloth_daily', 'label': '滤布日用', 'type': 'number', 'unit': '米', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'high_temp_tape_daily', 'label': '高温胶带日用', 'type': 'number', 'unit': '卷', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'regen_oil_out', 'label': '再生油出', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'regen_oil_in', 'label': '再生油回', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
    ],
    'finishing': [
        {'name': 'rolling_oil_per_ton', 'label': '轧制油吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'd40_per_ton', 'label': 'D40吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'steel_plate_per_ton', 'label': '钢板吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'steel_strip_per_ton', 'label': '钢带吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'steel_buckle_per_ton', 'label': '钢带扣吨耗', 'type': 'number', 'unit': 'kg', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
        {'name': 'high_temp_tape_daily', 'label': '高温胶带日用', 'type': 'number', 'unit': '卷', 'required': False, 'role_write': ['consumable_stat'], 'role_read': ['consumable_stat', 'admin', 'manager']},
    ],
}

CONTRACT_OWNER_FIELDS = [
    {
        'name': 'contract_no',
        'label': '合同号',
        'type': 'text',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科维护合同挂接信息。',
    },
    {
        'name': 'customer_name',
        'label': '客户名称',
        'type': 'text',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科维护客户归属。',
    },
    {
        'name': 'contract_weight',
        'label': '合同重量',
        'type': 'number',
        'unit': 'kg',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科维护合同口径。',
    },
]

QC_OWNER_FIELDS = [
    {
        'name': 'qc_grade',
        'label': '质检结论',
        'type': 'text',
        'required': False,
        'role_write': ['qc'],
        'role_read': ['qc', 'admin', 'manager'],
        'hint': '由质检岗位补录本班结论。',
    },
    {
        'name': 'qc_notes',
        'label': '质检备注',
        'type': 'text',
        'required': False,
        'role_write': ['qc'],
        'role_read': ['qc', 'admin', 'manager'],
        'hint': '由质检岗位补录异常说明。',
    },
]

INVENTORY_OWNER_FIELDS = [
    {
        'name': 'storage_inbound_weight',
        'label': '入库成品',
        'type': 'number',
        'unit': '吨',
        'required': True,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录当日入库成品。'
    },
    {
        'name': 'storage_inbound_area',
        'label': '入库面积',
        'type': 'number',
        'unit': '㎡',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录当日入库面积。'
    },
    {
        'name': 'plant_to_park_inbound_weight',
        'label': '本厂区入园区库',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录本厂区转入园区成品库重量。'
    },
    {
        'name': 'park_to_storage_inbound_weight',
        'label': '园区入成品库',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录园区入成品库重量。'
    },
    {
        'name': 'month_to_date_inbound_weight',
        'label': '月累计入库',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录月累计入库成品。'
    },
    {
        'name': 'month_to_date_inbound_area',
        'label': '月累计入库面积',
        'type': 'number',
        'unit': '㎡',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录月累计入库面积。'
    },
    {
        'name': 'shipment_weight',
        'label': '对外发货',
        'type': 'number',
        'unit': '吨',
        'required': True,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录当日发货重量。'
    },
    {
        'name': 'shipment_area',
        'label': '发货面积',
        'type': 'number',
        'unit': '㎡',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录当日发货面积。'
    },
    {
        'name': 'month_to_date_shipment_weight',
        'label': '月累计发货',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录月累计对外发货重量。'
    },
    {
        'name': 'month_to_date_shipment_area',
        'label': '月累计发货面积',
        'type': 'number',
        'unit': '㎡',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录月累计对外发货面积。'
    },
    {
        'name': 'consignment_weight',
        'label': '寄存吨位',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录寄存重量。'
    },
    {
        'name': 'finished_inventory_weight',
        'label': '成品库存',
        'type': 'number',
        'unit': '吨',
        'required': True,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录库存结存。'
    },
    {
        'name': 'shearing_prepared_weight',
        'label': '剪切备料',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['inventory_keeper'],
        'role_read': ['inventory_keeper', 'admin', 'manager'],
        'hint': '由成品库负责人补录剪切备料重量。'
    },
]

UTILITY_OWNER_FIELDS = [
    {
        'name': 'total_electricity_kwh',
        'label': '全厂用电',
        'type': 'number',
        'unit': 'kWh',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录全厂总用电量。'
    },
    {
        'name': 'new_plant_electricity_kwh',
        'label': '新厂用电',
        'type': 'number',
        'unit': 'kWh',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录新厂用电量。'
    },
    {
        'name': 'park_electricity_kwh',
        'label': '园区用电',
        'type': 'number',
        'unit': 'kWh',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录园区用电量。'
    },
    {
        'name': 'cast_roll_gas_m3',
        'label': '铸轧用气',
        'type': 'number',
        'unit': 'm³',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录铸轧分厂天然气用量。'
    },
    {
        'name': 'smelting_gas_m3',
        'label': '熔炼炉用气',
        'type': 'number',
        'unit': 'm³',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录铸锭熔炼炉天然气用量。'
    },
    {
        'name': 'heating_furnace_gas_m3',
        'label': '加热炉用气',
        'type': 'number',
        'unit': 'm³',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录热轧加热炉天然气用量。'
    },
    {
        'name': 'boiler_gas_m3',
        'label': '锅炉用气',
        'type': 'number',
        'unit': 'm³',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录锅炉天然气用量。'
    },
    {
        'name': 'total_gas_m3',
        'label': '天然气总量',
        'type': 'number',
        'unit': 'm³',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录天然气总量。'
    },
    {
        'name': 'groundwater_ton',
        'label': '地下水',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录地下水使用量。'
    },
    {
        'name': 'tap_water_ton',
        'label': '自来水',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['utility_manager'],
        'role_read': ['utility_manager', 'admin', 'manager'],
        'hint': '由水电气负责人补录自来水使用量。'
    },
]

CONTRACT_PROGRESS_FIELDS = [
    {
        'name': 'daily_contract_weight',
        'label': '当日接合同',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录当日合同量。'
    },
    {
        'name': 'daily_hot_roll_contract_weight',
        'label': '当日热轧合同',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录当日热轧合同量。'
    },
    {
        'name': 'month_to_date_contract_weight',
        'label': '月累计合同',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录月累计合同量。'
    },
    {
        'name': 'month_to_date_hot_roll_contract_weight',
        'label': '月累计热轧合同',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录月累计热轧合同量。'
    },
    {
        'name': 'remaining_contract_weight',
        'label': '余合同量',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录余合同量。'
    },
    {
        'name': 'remaining_hot_roll_contract_weight',
        'label': '余热轧合同',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录余热轧合同量。'
    },
    {
        'name': 'remaining_contract_delta_weight',
        'label': '余合同较昨日',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录余合同较昨日变化量。'
    },
    {
        'name': 'billet_inventory_weight',
        'label': '坯料总量',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录坯料总量。'
    },
    {
        'name': 'daily_input_weight',
        'label': '当日投料',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录当日投料重量。'
    },
    {
        'name': 'month_to_date_input_weight',
        'label': '月累计投料',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['contracts'],
        'role_read': ['contracts', 'admin', 'manager'],
        'hint': '由计划科负责人补录月累计投料重量。'
    },
]

DEFAULT_WORKSHOP_TEMPLATES = {
    'cold_roll': {
        'display_name': '冷轧车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '上机规格', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'alloy_grade', 'label': '合金成分', 'type': 'select', 'required': True, 'options_source': 'alloy_grades', 'hint': '如 5052, 3003'},
            {'name': 'material_state', 'label': '状态', 'type': 'select', 'required': False, 'options_source': 'material_states', 'hint': '如 O, H14, T4'},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_spec', 'label': '下机规格', 'type': 'spec', 'required': False, 'hint': '()×()×()'},
            {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
        ],
        'shift_fields': [],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *HYDRAULIC_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight - spool_weight',
                'hidden': True,
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': False,
    },
    'hot_roll': {
        'display_name': '热轧车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'alloy_grade', 'label': '合金牌号', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
            {'name': 'furnace_no', 'label': '炉次号', 'type': 'text', 'required': False},
            {'name': 'ingot_spec', 'label': '铸锭规格(mm)', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'input_weight', 'label': '上机锭重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_weight', 'label': '下机卷重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'trim_weight', 'label': '切头重量', 'type': 'number', 'unit': 'kg', 'required': False},
        ],
        'shift_fields': [],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *HYDRAULIC_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight - trim_weight',
                'hidden': True,
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': True,
    },
    'finishing': {
        'display_name': '精整车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '规格', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
            {'name': 'material_state', 'label': '状态', 'type': 'select', 'required': False, 'options_source': 'material_states'},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
        ],
        'shift_fields': [],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *HYDRAULIC_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight',
                'hidden': True,
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': False,
    },
    'shearing': {
        'display_name': '园区剪切车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '上机规格', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'alloy_grade', 'label': '成分', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
            {'name': 'material_state', 'label': '状态', 'type': 'select', 'required': False, 'options_source': 'material_states'},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_spec', 'label': '下机规格', 'type': 'spec', 'required': False, 'hint': '()×()×()'},
            {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
        ],
        'shift_fields': [],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *HYDRAULIC_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight - spool_weight',
                'hidden': True,
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': False,
    },
    'casting': {
        'display_name': '铸造车间',
        'tempo': 'slow',
        'entry_fields': [
            {'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
            {'name': 'ingot_spec', 'label': '规格', 'type': 'text', 'required': True, 'hint': '如 6×1600'},
            {'name': 'cast_speed', 'label': '速度', 'type': 'number', 'unit': 'mm/min', 'required': False},
            {'name': 'input_weight', 'label': '投入铝锭', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'scrap_weight', 'label': '废料', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'skin_weight', 'label': '皮料段', 'type': 'number', 'unit': 'kg', 'required': False},
        ],
        'shift_fields': [
            {'name': 'paper_furnace', 'label': '格纸炉', 'type': 'number', 'unit': 'kg'},
            {'name': 'static_furnace', 'label': '静置炉', 'type': 'number', 'unit': '°C'},
            {'name': 'unit_output', 'label': '单机产量', 'type': 'number', 'unit': 'kg'},
            {'name': 'gas_consumption', 'label': '当班耗气', 'type': 'number', 'unit': 'm³'},
        ],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *HYDRAULIC_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': True,
    },

    'straightening': {
        'display_name': '拉矫车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '规格', 'type': 'spec', 'required': True, 'hint': '()×()×C', 'spec_suffix': 'C'},
            {'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
            {'name': 'material_state', 'label': '状态', 'type': 'select', 'required': False, 'options_source': 'material_states'},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'tray_weight', 'label': '托盘重量', 'type': 'number', 'unit': 'kg', 'required': False},
        ],
        'shift_fields': [],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *HYDRAULIC_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight - spool_weight - tray_weight',
                'hidden': True,
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': False,
    },
    'inventory': {
        'display_name': '成品库与公辅',
        'tempo': 'fast',
        'entry_fields': INVENTORY_OWNER_FIELDS,
        'shift_fields': [],
        'extra_fields': [
            *UTILITY_OWNER_FIELDS,
            *CONTRACT_PROGRESS_FIELDS,
        ],
        'qc_fields': [],
        'readonly_fields': [
            {
                'name': 'actual_inventory_weight',
                'label': '实际库存',
                'type': 'number',
                'unit': '吨',
                'compute': 'finished_inventory_weight - consignment_weight',
                'role_read': ['inventory_keeper', 'admin', 'manager'],
            },
        ],
        'supports_ocr': False,
    },
    'annealing': {
        'display_name': '在线退火车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
            {'name': 'input_spec', 'label': '上机规格', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
        ],
        'shift_fields': [],
        'extra_fields': [
            *ENERGY_OWNER_FIELDS,
            *MAINTENANCE_OWNER_FIELDS,
            *CONTRACT_OWNER_FIELDS,
        ],
        'qc_fields': QC_OWNER_FIELDS,
        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight',
                'hidden': True,
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
                'hidden': True,
            },
        ],
        'supports_ocr': False,
    },
}

WORKSHOP_TEMPLATES = DEFAULT_WORKSHOP_TEMPLATES

_POWER_ROLES = frozenset({'admin', 'manager', 'factory_director'})


import sys
from types import ModuleType

from app.core.templates import loader as loader
from app.core.templates import permissions as permissions
from app.core.templates import resolver as resolver

_MODULES = (resolver, loader, permissions)
_PUBLIC_ALL = ['WORK_ORDER_FIELD_NAMES', 'WORK_ORDER_ENTRY_FIELD_NAMES', 'NUMERIC_FIELD_NAMES', 'TIME_FIELD_NAMES', 'WORKSHOP_TYPE_BY_WORKSHOP_CODE', 'WORKSHOP_TYPE_ALIASES', 'ENERGY_OWNER_FIELDS', 'MAINTENANCE_OWNER_FIELDS', 'HYDRAULIC_OWNER_FIELDS', 'CONSUMABLE_OWNER_FIELDS', 'CONTRACT_OWNER_FIELDS', 'QC_OWNER_FIELDS', 'INVENTORY_OWNER_FIELDS', 'UTILITY_OWNER_FIELDS', 'CONTRACT_PROGRESS_FIELDS', 'DEFAULT_WORKSHOP_TEMPLATES', 'WORKSHOP_TEMPLATES', 'normalize_workshop_type', 'normalize_template_key', 'resolve_template_key', 'resolve_workshop_type', 'get_workshop_template_definition', 'normalize_template_definition_payload', 'get_workshop_template', '_merge_supplemental_sections']


def _all_names() -> set[str]:
    names: set[str] = {
        name for name in globals()
        if not name.startswith('__') and name not in {'annotations', 'ModuleType', 'sys'}
    }
    for module in _MODULES:
        names.update(
            name for name in module.__dict__
            if not name.startswith('__') and name != 'annotations'
        )
    return names


def _refresh_exports() -> None:
    namespace = {
        name: value
        for name, value in globals().items()
        if not name.startswith('__') and name not in {'annotations', 'ModuleType', 'sys'}
    }
    for module in _MODULES:
        for name, value in module.__dict__.items():
            if not name.startswith('__') and name != 'annotations':
                namespace.setdefault(name, value)
    for module in _MODULES:
        for name, value in namespace.items():
            module.__dict__.setdefault(name, value)
    globals().update(namespace)


class _CompatModule(ModuleType):
    def __getattr__(self, name: str):
        for module in _MODULES:
            if name in module.__dict__:
                return module.__dict__[name]
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value) -> None:
        for module in _MODULES:
            if name in module.__dict__:
                module.__dict__[name] = value
        globals()[name] = value
        super().__setattr__(name, value)


_refresh_exports()
sys.modules[__name__].__class__ = _CompatModule

__all__ = _PUBLIC_ALL
