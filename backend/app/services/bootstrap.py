from datetime import time

from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_password_hash
from app.models.imports import FieldMappingTemplate
from app.models.shift import ShiftConfig
from app.models.system import SystemConfig, User


DEFAULT_SYSTEM_CONFIGS = [
    ('system_name', '河南鑫泰铝业生产管理系统', '系统显示名称'),
    ('default_timezone', 'Asia/Shanghai', '默认时区'),
    ('import_mode', 'file', '导入模式'),
    ('dingtalk_enabled', 'false', '是否启用钉钉集成'),
]

DEFAULT_SHIFT_CONFIGS = [
    ('A', '白班', 'day', time(7, 0), time(15, 0), False, 0, 1),
    ('B', '小夜', 'evening', time(15, 0), time(23, 0), True, 0, 2),
    ('C', '大夜', 'night', time(23, 0), time(7, 0), True, -1, 3),
]

DEFAULT_FIELD_MAPPING_TEMPLATES = [
    {
        'template_code': 'attendance_schedule_default',
        'template_name': '考勤排班默认模板',
        'import_type': 'attendance_schedule',
        'source_type': 'attendance_schedule',
        'mappings': {
            'employee_no': 'employee_no',
            'dingtalk_user_id': 'dingtalk_user_id',
            'schedule_date': 'schedule_date',
            'shift_code': 'shift_code',
            'team_code': 'team_code',
            'workshop_code': 'workshop_code',
        },
        'description': '考勤排班导入字段默认映射模板',
    },
    {
        'template_code': 'attendance_clock_default',
        'template_name': '考勤打卡默认模板',
        'import_type': 'attendance_clock',
        'source_type': 'attendance_clock',
        'mappings': {
            'employee_no': 'employee_no',
            'dingtalk_user_id': 'dingtalk_user_id',
            'clock_datetime': 'clock_datetime',
            'clock_type': 'clock_type',
            'dingtalk_record_id': 'dingtalk_record_id',
            'device_id': 'device_id',
            'location_name': 'location_name',
        },
        'description': '考勤打卡导入字段默认映射模板',
    },
    {
        'template_code': 'production_shift_default',
        'template_name': '班次产量默认模板',
        'import_type': 'production_shift',
        'source_type': 'production_shift',
        'mappings': {
            'business_date': 'business_date',
            'shift_code': 'shift_code',
            'workshop_code': 'workshop_code',
            'team_code': 'team_code',
            'equipment_code': 'equipment_code',
            'input_weight': 'input_weight',
            'output_weight': 'output_weight',
            'qualified_weight': 'qualified_weight',
            'scrap_weight': 'scrap_weight',
            'downtime_minutes': 'downtime_minutes',
            'downtime_reason': 'downtime_reason',
            'issue_count': 'issue_count',
            'electricity_kwh': 'electricity_kwh',
            'planned_headcount': 'planned_headcount',
            'notes': 'notes',
        },
        'description': '班次产量导入字段默认映射模板',
    },
    {
        'template_code': 'energy_default',
        'template_name': '能耗默认模板',
        'import_type': 'energy',
        'source_type': 'energy',
        'mappings': {
            'business_date': {'source': ['business_date', 'date'], 'required': True, 'transform_rule': 'date'},
            'workshop_code': {'source': ['workshop_code', 'workshop'], 'required': True, 'transform_rule': 'strip|upper'},
            'shift_code': {'source': ['shift_code', 'shift'], 'required': True, 'transform_rule': 'strip|upper'},
            'energy_type': {'source': ['energy_type', 'type'], 'required': True, 'transform_rule': 'strip|lower'},
            'energy_value': {'source': ['energy_value', 'value'], 'required': True, 'transform_rule': 'float'},
            'unit': {'source': ['unit'], 'required': False, 'transform_rule': 'strip'},
            'source_row_no': {'source': ['source_row_no', 'row_no'], 'required': False, 'transform_rule': 'int'},
        },
        'description': '能耗导入字段默认映射模板',
    },
    {
        'template_code': 'mes_export_default',
        'template_name': 'MES导出默认模板',
        'import_type': 'mes_export',
        'source_type': 'mes_export',
        'mappings': {
            'business_date': {'source': ['business_date', 'date'], 'required': True, 'transform_rule': 'date'},
            'workshop_code': {'source': ['workshop_code', 'workshop'], 'required': True, 'transform_rule': 'strip|upper'},
            'shift_code': {'source': ['shift_code', 'shift'], 'required': True, 'transform_rule': 'strip|upper'},
            'metric_code': {'source': ['metric_code', 'metric'], 'required': True, 'transform_rule': 'strip'},
            'metric_name': {'source': ['metric_name', 'metric_name_cn'], 'required': False, 'transform_rule': 'strip'},
            'metric_value': {'source': ['metric_value', 'value'], 'required': True, 'transform_rule': 'float'},
            'unit': {'source': ['unit'], 'required': False, 'transform_rule': 'strip'},
            'source_row_no': {'source': ['source_row_no', 'row_no'], 'required': False, 'transform_rule': 'int'},
        },
        'description': 'MES导出字段默认映射模板',
    },
]


def seed_system_configs(db: Session) -> None:
    existing = {item.config_key: item for item in db.query(SystemConfig).all()}
    for key, value, description in DEFAULT_SYSTEM_CONFIGS:
        item = existing.get(key)
        if item is None:
            db.add(
                SystemConfig(
                    config_key=key,
                    config_value=value,
                    config_type='string',
                    description=description,
                )
            )
            continue
        item.config_value = value
        item.config_type = 'string'
        item.description = description
    db.commit()


def seed_shift_configs(db: Session) -> None:
    existing = {item.code: item for item in db.query(ShiftConfig).all()}
    for code, name, shift_type, start_time, end_time, is_cross_day, offset, sort_order in DEFAULT_SHIFT_CONFIGS:
        item = existing.get(code)
        if item is None:
            db.add(
                ShiftConfig(
                    code=code,
                    name=name,
                    shift_type=shift_type,
                    start_time=start_time,
                    end_time=end_time,
                    is_cross_day=is_cross_day,
                    business_day_offset=offset,
                    late_tolerance_minutes=30,
                    early_tolerance_minutes=30,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            continue
        item.name = name
        item.shift_type = shift_type
        item.start_time = start_time
        item.end_time = end_time
        item.is_cross_day = is_cross_day
        item.business_day_offset = offset
        item.late_tolerance_minutes = 30
        item.early_tolerance_minutes = 30
        item.sort_order = sort_order
        item.is_active = True
    db.commit()


def seed_field_mapping_templates(db: Session) -> None:
    existing = {item.template_code: item for item in db.query(FieldMappingTemplate).all()}
    for template in DEFAULT_FIELD_MAPPING_TEMPLATES:
        item = existing.get(template['template_code'])
        if item is None:
            db.add(
                FieldMappingTemplate(
                    template_code=template['template_code'],
                    template_name=template['template_name'],
                    import_type=template['import_type'],
                    source_type=template.get('source_type'),
                    mappings=template['mappings'],
                    description=template['description'],
                    is_active=True,
                )
            )
            continue
        item.template_name = template['template_name']
        item.import_type = template['import_type']
        item.source_type = template.get('source_type')
        item.mappings = template['mappings']
        item.description = template['description']
        item.is_active = True
    db.commit()


def ensure_admin_user(db: Session) -> User:
    user = db.query(User).filter(User.username == settings.INIT_ADMIN_USERNAME).first()
    if user:
        user.password_hash = get_password_hash(settings.INIT_ADMIN_PASSWORD)
        user.name = settings.INIT_ADMIN_NAME
        user.role = 'admin'
        user.data_scope_type = 'all'
        user.assigned_shift_ids = None
        user.is_mobile_user = False
        user.is_reviewer = True
        user.is_manager = True
        user.is_active = True
    else:
        user = User(
            username=settings.INIT_ADMIN_USERNAME,
            password_hash=get_password_hash(settings.INIT_ADMIN_PASSWORD),
            name=settings.INIT_ADMIN_NAME,
            role='admin',
            data_scope_type='all',
            assigned_shift_ids=None,
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user
