from types import SimpleNamespace

from app.models.imports import FieldMappingTemplate
from app.models.shift import ShiftConfig
from app.models.system import SystemConfig
from app.services.bootstrap import (
    seed_field_mapping_templates,
    seed_shift_configs,
    seed_system_configs,
)


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _FakeDB:
    def __init__(self, mapping):
        self._mapping = mapping

    def query(self, model):
        return _FakeQuery(self._mapping.setdefault(model, []))

    def add(self, item):
        self._mapping.setdefault(type(item), []).append(item)

    def commit(self):
        return None


def test_seed_system_configs_updates_existing_values() -> None:
    existing = SimpleNamespace(
        config_key='system_name',
        config_value='Old Name',
        config_type='string',
        description='Old Description',
    )
    db = _FakeDB({SystemConfig: [existing]})

    seed_system_configs(db)

    assert existing.config_value == '河南鑫泰铝业生产管理系统'
    assert existing.description == '系统显示名称'


def test_seed_shift_configs_updates_existing_shift_name_and_times() -> None:
    existing = SimpleNamespace(
        code='A',
        name='Day Shift',
        shift_type='day',
        start_time=None,
        end_time=None,
        is_cross_day=True,
        business_day_offset=99,
        late_tolerance_minutes=30,
        early_tolerance_minutes=30,
        sort_order=99,
        is_active=False,
    )
    db = _FakeDB({ShiftConfig: [existing]})

    seed_shift_configs(db)

    assert existing.name == '白班'
    assert str(existing.start_time) == '07:00:00'
    assert str(existing.end_time) == '15:00:00'
    assert existing.is_cross_day is False
    assert existing.business_day_offset == 0
    assert existing.sort_order == 1
    assert existing.is_active is True


def test_seed_field_mapping_templates_updates_existing_template_text() -> None:
    existing = SimpleNamespace(
        template_code='energy_default',
        template_name='Energy Default',
        import_type='energy',
        source_type='energy',
        mappings={},
        description='Old',
        is_active=False,
    )
    db = _FakeDB({FieldMappingTemplate: [existing]})

    seed_field_mapping_templates(db)

    assert existing.template_name == '能耗默认模板'
    assert existing.description == '能耗导入字段默认映射模板'
    assert existing.is_active is True
