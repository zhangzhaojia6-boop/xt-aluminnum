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
            {'name': 'input_spec', 'label': '上机规格', 'type': 'text', 'required': True, 'hint': '如 1.9×1200×C'},
            {'name': 'alloy_grade', 'label': '合金成分', 'type': 'text', 'required': True, 'hint': '如 5052, 3003'},
            {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False, 'hint': '如 O, H14, T4'},
            {'name': 'on_machine_time', 'label': '上机时间', 'type': 'time', 'required': False},
            {'name': 'off_machine_time', 'label': '下机时间', 'type': 'time', 'required': False},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_spec', 'label': '下机规格', 'type': 'text', 'required': False},
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
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
            },
        ],
        'supports_ocr': False,
    },
    'hot_roll': {
        'display_name': '热轧车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'alloy_grade', 'label': '合金牌号', 'type': 'text', 'required': True},
            {'name': 'furnace_no', 'label': '炉次号', 'type': 'text', 'required': True},
            {'name': 'ingot_spec', 'label': '铸锭规格(mm)', 'type': 'text', 'required': True, 'hint': '如 450×1600×5900'},
            {'name': 'on_machine_time', 'label': '上机时间', 'type': 'time', 'required': False},
            {'name': 'off_machine_time', 'label': '下机时间', 'type': 'time', 'required': False},
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
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
            },
        ],
        'supports_ocr': True,
    },
    'finishing': {
        'display_name': '\u7cbe\u6574\u8f66\u95f4',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '\u6279\u53f7', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '\u89c4\u683c', 'type': 'text', 'required': True},
            {'name': 'alloy_grade', 'label': '\u5408\u91d1', 'type': 'text', 'required': True},
            {'name': 'material_state', 'label': '\u72b6\u6001', 'type': 'text', 'required': False},
            {'name': 'on_machine_time', 'label': '\u4e0a\u673a\u65f6\u95f4', 'type': 'time', 'required': False},
            {'name': 'input_weight', 'label': '\u4e0a\u673a\u91cd\u91cf', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'spool_weight', 'label': '\u5957\u7b52\u91cd\u91cf', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'off_machine_time', 'label': '\u4e0b\u673a\u65f6\u95f4', 'type': 'time', 'required': False},
            {'name': 'output_weight', 'label': '\u4e0b\u673a\u91cd\u91cf', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'tray_weight', 'label': '\u6258\u76d8\u91cd\u91cf', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'scrap_weight', 'label': '\u5e9f\u6599\u91cd\u91cf', 'type': 'number', 'unit': 'kg', 'required': False},
        ],
        'shift_fields': [
            {'name': 'roll_speed', 'label': '机列速度', 'type': 'number', 'unit': 'm/min'},
            {'name': 'ring_count', 'label': '圈/球', 'type': 'text'},
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
            },
        ],
        'supports_ocr': False,
    },
    'shearing': {
        'display_name': '园区剪切车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '上机规格', 'type': 'text', 'required': True},
            {'name': 'alloy_grade', 'label': '成分', 'type': 'text', 'required': True},
            {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False},
            {'name': 'on_machine_time', 'label': '上机时间', 'type': 'time', 'required': False},
            {'name': 'off_machine_time', 'label': '下机时间', 'type': 'time', 'required': False},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_spec', 'label': '下机规格', 'type': 'text', 'required': False},
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
            },
            {
                'name': 'yield_rate',
                'label': '成品率',
                'type': 'number',
                'unit': '%',
                'compute': 'output_weight / input_weight * 100',
            },
        ],
        'supports_ocr': False,
    },
    'casting': {
        'display_name': '铸造车间',
        'tempo': 'slow',
        'entry_fields': [
            {'name': 'alloy_grade', 'label': '合金', 'type': 'text', 'required': True},
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
            },
        ],
        'supports_ocr': True,
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
}

WORKSHOP_TEMPLATES = DEFAULT_WORKSHOP_TEMPLATES


def _listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _field_type(field_name: str, explicit_type: str | None = None) -> str:
    if explicit_type:
        return explicit_type
    if field_name in TIME_FIELD_NAMES:
        return 'time'
    if field_name in NUMERIC_FIELD_NAMES:
        return 'number'
    return 'text'


def _field_target(section_name: str, field_name: str) -> str:
    if field_name in WORK_ORDER_FIELD_NAMES:
        return 'work_order'
    if section_name == 'qc_fields':
        return 'qc'
    if field_name in WORK_ORDER_ENTRY_FIELD_NAMES:
        return 'entry'
    return 'extra'


def _default_write_roles(section_name: str, field_name: str, target: str) -> list[str]:
    if target == 'work_order':
        return []
    if target == 'entry':
        if field_name in {'energy_kwh', 'gas_m3'}:
            return ['energy_stat']
        return []
    if target == 'qc':
        return ['qc']
    return ['shift_leader']


def _default_read_roles(section_name: str, target: str, field_name: str) -> list[str]:
    if section_name == 'shift_fields':
        return ['shift_leader', 'admin', 'manager']
    if target in {'extra', 'qc'}:
        return [READ_ALL]
    if target in {'work_order', 'entry'}:
        return []
    return [READ_ALL]


def _is_readable(target: str, field_name: str, read_roles: list[str], user_role: str) -> bool:
    normalized_role = normalize_role(user_role)
    normalized_rules = {normalize_role(item) for item in read_roles}
    if READ_ALL in normalized_rules or normalized_role in normalized_rules:
        return True
    if target == 'work_order':
        return field_name in set(get_readable_fields('work_orders', user_role))
    if target == 'entry':
        return field_name in set(get_readable_fields('work_order_entries', user_role))
    return False


def _is_writable(target: str, field_name: str, write_roles: list[str], user_role: str) -> bool:
    normalized_role = normalize_role(user_role)
    normalized_rules = {normalize_role(item) for item in write_roles}
    if READ_ALL in normalized_rules or normalized_role in normalized_rules:
        return True
    if target == 'work_order':
        return check_field_write('work_orders', field_name, user_role)
    if target == 'entry':
        return check_field_write('work_order_entries', field_name, user_role)
    return False


def _normalize_field(
    section_name: str,
    field: dict[str, Any],
    user_role: str,
    *,
    force_readonly: bool = False,
) -> tuple[dict[str, Any], bool, bool]:
    normalized = deepcopy(field)
    field_name = normalized['name']
    target = _field_target(section_name, field_name)
    write_roles = _listify(normalized.get('role_write')) or _default_write_roles(section_name, field_name, target)
    read_roles = _listify(normalized.get('role_read')) or _default_read_roles(section_name, target, field_name)

    normalized['type'] = _field_type(field_name, normalized.get('type'))
    normalized['target'] = target
    normalized['section'] = section_name
    normalized['role_write'] = write_roles
    normalized['role_read'] = read_roles
    normalized['compute'] = normalized.get('compute')

    readable = _is_readable(target, field_name, read_roles, user_role)
    if force_readonly:
        normalized['editable'] = False
        normalized['readonly'] = readable
        return normalized, False, readable

    writable = _is_writable(target, field_name, write_roles, user_role)
    normalized['editable'] = writable
    normalized['readonly'] = readable and not writable
    return normalized, writable, readable


def normalize_workshop_type(workshop_type: str | None) -> str | None:
    raw_value = (workshop_type or '').strip().lower()
    if not raw_value:
        return None
    return WORKSHOP_TYPE_ALIASES.get(raw_value, raw_value)


def normalize_template_key(template_key: str | None) -> str | None:
    raw_value = (template_key or '').strip()
    if not raw_value:
        return None

    normalized_type = normalize_workshop_type(raw_value)
    if normalized_type in DEFAULT_WORKSHOP_TEMPLATES:
        return normalized_type

    uppercase_value = raw_value.upper()
    if uppercase_value in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
        return uppercase_value

    return uppercase_value


def resolve_template_key(
    *,
    template_key: str | None = None,
    workshop_type: str | None = None,
    workshop_code: str | None = None,
    workshop_name: str | None = None,
) -> tuple[str, str]:
    normalized_key = normalize_template_key(template_key)
    if normalized_key:
        if normalized_key in DEFAULT_WORKSHOP_TEMPLATES:
            return normalized_key, normalized_key
        if normalized_key in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
            return normalized_key, resolve_workshop_type(
                workshop_type=WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(normalized_key),
                workshop_code=normalized_key,
                workshop_name=workshop_name,
            )

    base_type = resolve_workshop_type(
        workshop_type=workshop_type,
        workshop_code=workshop_code,
        workshop_name=workshop_name,
    )
    if workshop_code and workshop_code.strip().upper() in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
        return workshop_code.strip().upper(), base_type
    return base_type, base_type


def _normalize_definition_field(field: dict[str, Any], *, section_name: str) -> dict[str, Any]:
    normalized = deepcopy(field)
    normalized['name'] = str(normalized.get('name') or '').strip()
    normalized['label'] = str(normalized.get('label') or normalized['name']).strip()
    normalized['type'] = _field_type(normalized['name'], normalized.get('type'))
    normalized['required'] = bool(normalized.get('required', False))
    normalized['unit'] = str(normalized.get('unit') or '').strip() or None
    normalized['hint'] = str(normalized.get('hint') or '').strip() or None
    normalized['compute'] = str(normalized.get('compute') or '').strip() or None
    normalized['enabled'] = bool(normalized.get('enabled', True))
    normalized['section'] = section_name
    return normalized


def _normalize_definition_section(fields: list[dict[str, Any]] | None, *, section_name: str) -> list[dict[str, Any]]:
    return [
        _normalize_definition_field(field, section_name=section_name)
        for field in (fields or [])
        if str(field.get('name') or '').strip()
    ]


def _split_supplemental_sections(fields: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    shift_fields: list[dict[str, Any]] = []
    extra_fields: list[dict[str, Any]] = []

    for field in fields or []:
        stored_section = str(field.get('section') or '').strip()
        if stored_section == 'shift_fields':
            shift_fields.append(field)
            continue
        extra_fields.append(field)

    return shift_fields, extra_fields


def _merge_supplemental_sections(
    *,
    shift_fields: list[dict[str, Any]] | None,
    extra_fields: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged = []
    merged.extend(_normalize_definition_section(shift_fields, section_name='shift_fields'))
    merged.extend(_normalize_definition_section(extra_fields, section_name='extra_fields'))
    return merged


def _load_template_definition_from_config(config: WorkshopTemplateConfig) -> dict[str, Any]:
    shift_fields, extra_fields = _split_supplemental_sections(config.extra_fields)
    return {
        'display_name': config.display_name,
        'tempo': config.tempo,
        'supports_ocr': bool(config.supports_ocr),
        'entry_fields': _normalize_definition_section(config.entry_fields, section_name='entry_fields'),
        'shift_fields': _normalize_definition_section(shift_fields, section_name='shift_fields'),
        'extra_fields': _normalize_definition_section(extra_fields, section_name='extra_fields'),
        'qc_fields': _normalize_definition_section(config.qc_fields, section_name='qc_fields'),
        'readonly_fields': _normalize_definition_section(config.readonly_fields, section_name='readonly_fields'),
    }


def _load_default_template_definition(base_type: str) -> dict[str, Any]:
    template = deepcopy(DEFAULT_WORKSHOP_TEMPLATES[base_type])
    return {
        'display_name': template['display_name'],
        'tempo': template['tempo'],
        'supports_ocr': bool(template.get('supports_ocr', False)),
        'entry_fields': _normalize_definition_section(template.get('entry_fields'), section_name='entry_fields'),
        'shift_fields': _normalize_definition_section(template.get('shift_fields'), section_name='shift_fields'),
        'extra_fields': _normalize_definition_section(template.get('extra_fields'), section_name='extra_fields'),
        'qc_fields': _normalize_definition_section(template.get('qc_fields'), section_name='qc_fields'),
        'readonly_fields': _normalize_definition_section(template.get('readonly_fields'), section_name='readonly_fields'),
    }


def get_workshop_template_definition(
    template_key: str,
    *,
    db: Session | None = None,
    workshop_type: str | None = None,
    workshop_code: str | None = None,
    workshop_name: str | None = None,
) -> dict[str, Any]:
    canonical_key, base_type = resolve_template_key(
        template_key=template_key,
        workshop_type=workshop_type,
        workshop_code=workshop_code,
        workshop_name=workshop_name,
    )

    config = None
    if db is not None and hasattr(db, 'query'):
        config = (
            db.query(WorkshopTemplateConfig)
            .filter(
                WorkshopTemplateConfig.template_key == canonical_key,
                WorkshopTemplateConfig.is_active.is_(True),
            )
            .first()
        )

    definition = _load_template_definition_from_config(config) if config is not None else _load_default_template_definition(base_type)
    return {
        'template_key': canonical_key,
        'workshop_type': base_type,
        'source_template_key': canonical_key if config is not None else base_type,
        'has_override': config is not None,
        **definition,
    }


def normalize_template_definition_payload(
    template_key: str,
    payload: dict[str, Any],
    *,
    db: Session | None = None,
) -> dict[str, Any]:
    definition = get_workshop_template_definition(template_key, db=db)
    return {
        'template_key': definition['template_key'],
        'workshop_type': definition['workshop_type'],
        'display_name': str(payload.get('display_name') or definition['display_name']).strip() or definition['display_name'],
        'tempo': str(payload.get('tempo') or definition['tempo']).strip() or definition['tempo'],
        'supports_ocr': bool(payload.get('supports_ocr', definition['supports_ocr'])),
        'entry_fields': _normalize_definition_section(payload.get('entry_fields'), section_name='entry_fields'),
        'shift_fields': _normalize_definition_section(payload.get('shift_fields'), section_name='shift_fields'),
        'extra_fields': _normalize_definition_section(payload.get('extra_fields'), section_name='extra_fields'),
        'qc_fields': _normalize_definition_section(payload.get('qc_fields'), section_name='qc_fields'),
        'readonly_fields': _normalize_definition_section(payload.get('readonly_fields'), section_name='readonly_fields'),
    }


def resolve_workshop_type(
    *,
    workshop_type: str | None = None,
    workshop_code: str | None,
    workshop_name: str | None,
) -> str:
    normalized_type = normalize_workshop_type(workshop_type)
    if normalized_type in WORKSHOP_TEMPLATES:
        return normalized_type

    code = (workshop_code or '').strip().upper()
    normalized_code = normalize_workshop_type((workshop_code or '').strip().lower())
    name = (workshop_name or '').strip()

    if normalized_code in WORKSHOP_TEMPLATES:
        return normalized_code

    mapped_type = WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(code)
    if mapped_type in WORKSHOP_TEMPLATES:
        return mapped_type

    lowered_name = name.lower()
    if '2050' in code or '2050' in name or '1450' in code or '1450' in name or code.startswith('LZ'):
        return 'cold_roll'
    if code.startswith('ZR') or code == 'ZD' or '铸' in name:
        return 'casting'
    if code == 'RZ' or '热轧' in name:
        return 'hot_roll'
    if code.startswith('JZ') or '精整' in name:
        return 'finishing'
    if code == 'JQ' or '剪切' in name:
        return 'shearing'
    if code == 'CPK' or '成品库' in name or '库存' in name:
        return 'inventory'
    if 'cold' in lowered_name:
        return 'cold_roll'
    if 'finish' in lowered_name:
        return 'finishing'
    if 'shear' in lowered_name or 'cut' in lowered_name:
        return 'shearing'
    if 'hot' in lowered_name:
        return 'hot_roll'
    if 'inventory' in lowered_name or 'warehouse' in lowered_name:
        return 'inventory'
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='workshop template not found')


_POWER_ROLES = frozenset({'admin', 'manager', 'factory_director'})


def get_workshop_template(workshop_type: str, *, user_role: str, db: Session | None = None) -> dict[str, Any]:
    template = get_workshop_template_definition(workshop_type, db=db)

    effective_role = normalize_role(user_role) or user_role
    is_power_user = effective_role in _POWER_ROLES or user_role in _POWER_ROLES

    readonly_fields: list[dict[str, Any]] = []
    result = {
        'template_key': template['template_key'],
        'workshop_type': template['workshop_type'],
        'display_name': template['display_name'],
        'tempo': template['tempo'],
        'supports_ocr': bool(template.get('supports_ocr', False)),
        'entry_fields': [],
        'shift_fields': [],
        'extra_fields': [],
        'qc_fields': [],
        'readonly_fields': readonly_fields,
    }

    for section_name in ['entry_fields', 'shift_fields', 'extra_fields', 'qc_fields']:
        for field in template.get(section_name, []):
            if not field.get('enabled', True):
                continue
            normalized, writable, readable = _normalize_field(section_name, field, user_role)
            normalized['enabled'] = True
            if is_power_user:
                normalized['editable'] = True
                normalized['readonly'] = False
                result[section_name].append(normalized)
            elif writable:
                result[section_name].append(normalized)
            elif readable:
                readonly_fields.append(normalized)

    for field in template.get('readonly_fields', []):
        if not field.get('enabled', True):
            continue
        normalized, _writable, readable = _normalize_field('readonly_fields', field, user_role, force_readonly=True)
        normalized['enabled'] = True
        if readable:
            readonly_fields.append(normalized)

    return result
