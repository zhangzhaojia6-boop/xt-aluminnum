"""Fix workshop templates: remove time fields, add spec type, auto-calc scrap, add straightening template."""
import re

filepath = 'backend/app/core/workshop_templates.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace finishing section
old = "    'finishing': {\n        'display_name': '精整车间',\n        'tempo': 'fast',\n        'entry_fields': [\n            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},\n            {'name': 'input_spec', 'label': '规格', 'type': 'text', 'required': True},\n            {'name': 'alloy_grade', 'label': '合金', 'type': 'text', 'required': True},\n            {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False},\n            {'name': 'on_machine_time', 'label': '上机时间', 'type': 'time', 'required': False},\n            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},\n            {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False},\n            {'name': 'off_machine_time', 'label': '下机时间', 'type': 'time', 'required': False},\n            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},\n            {'name': 'tray_weight', 'label': '托盘重量', 'type': 'number', 'unit': 'kg', 'required': False},\n            {'name': 'scrap_weight', 'label': '废料重量', 'type': 'number', 'unit': 'kg', 'required': False},\n        ],"

new = """    'finishing': {
        'display_name': '精整车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '规格', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'alloy_grade', 'label': '合金', 'type': 'text', 'required': True},
            {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'tray_weight', 'label': '托盘重量', 'type': 'number', 'unit': 'kg', 'required': False},
        ],"""

if old in content:
    content = content.replace(old, new)
    print('finishing entry_fields replaced')
else:
    print('ERROR: finishing entry_fields not found')

# 2. Replace finishing readonly_fields to add scrap_weight computed
old_ro = """        'readonly_fields': [
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
    'shearing': {"""

new_ro = """        'readonly_fields': [
            {
                'name': 'scrap_weight',
                'label': '废料重量',
                'type': 'number',
                'unit': 'kg',
                'compute': 'input_weight - output_weight - spool_weight - tray_weight',
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
    'shearing': {"""

if old_ro in content:
    content = content.replace(old_ro, new_ro)
    print('finishing readonly replaced')
else:
    print('ERROR: finishing readonly not found')

# 3. Replace shearing entry_fields - remove time, add spec type
old_sh = """    'shearing': {
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
        ],"""

new_sh = """    'shearing': {
        'display_name': '园区剪切车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '上机规格', 'type': 'spec', 'required': True, 'hint': '()×()×()'},
            {'name': 'alloy_grade', 'label': '成分', 'type': 'text', 'required': True},
            {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False},
            {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True},
            {'name': 'output_spec', 'label': '下机规格', 'type': 'spec', 'required': False, 'hint': '()×()×()'},
            {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False},
            {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True},
        ],"""

if old_sh in content:
    content = content.replace(old_sh, new_sh)
    print('shearing replaced')
else:
    print('ERROR: shearing not found')

# 4. Add 'straightening' (拉矫) template after shearing - same as finishing but spec last field fixed C
# Also add to WORKSHOP_TYPE_BY_WORKSHOP_CODE
old_code_map_end = "    'JZ2': 'finishing',"
new_code_map_end = "    'JZ2': 'straightening',"
if old_code_map_end in content:
    content = content.replace(old_code_map_end, new_code_map_end)
    print('JZ2 mapped to straightening')
else:
    print('ERROR: JZ2 mapping not found')

# Add straightening template after shearing closes
straightening_template = """
    'straightening': {
        'display_name': '拉矫车间',
        'tempo': 'fast',
        'entry_fields': [
            {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True},
            {'name': 'input_spec', 'label': '规格', 'type': 'spec', 'required': True, 'hint': '()×()×C', 'spec_suffix': 'C'},
            {'name': 'alloy_grade', 'label': '合金', 'type': 'text', 'required': True},
            {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False},
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
    },"""

# Insert after casting section
insert_marker = "    'inventory': {"
if insert_marker in content:
    content = content.replace(insert_marker, straightening_template + "\n" + insert_marker)
    print('straightening template added')
else:
    print('ERROR: inventory marker not found')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('All done')
