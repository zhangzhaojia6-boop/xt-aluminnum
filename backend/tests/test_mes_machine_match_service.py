from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import mes_machine_match_service


def _machine(
    *,
    machine_id: int,
    code: str,
    name: str,
    workshop_id: int,
    equipment_type: str,
):
    return SimpleNamespace(
        id=machine_id,
        code=code,
        name=name,
        workshop_id=workshop_id,
        equipment_type=equipment_type,
    )


def _terminal_binding(
    *,
    terminal_code: str,
    equipment_id: int,
    workshop_name: str | None = None,
    process_name: str | None = None,
    mes_device_name: str | None = None,
    is_active: bool = True,
    valid_from=None,
    valid_to=None,
):
    return SimpleNamespace(
        terminal_code=terminal_code,
        terminal_name=None,
        mes_device_name=mes_device_name,
        workshop_name=workshop_name,
        process_name=process_name,
        equipment_id=equipment_id,
        confidence='high',
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=is_active,
    )


def test_resolves_cold_mill_device_with_network_suffix_across_workshops() -> None:
    machines = [
        _machine(machine_id=11, code='LZ2050-1', name='2050#', workshop_id=5, equipment_type='cold_mill'),
        _machine(machine_id=12, code='LZ1650-1', name='1650#', workshop_id=18, equipment_type='cold_mill'),
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        device_name='1650冷轧（WAN）',
        process_hint='冷轧',
        preferred_workshop_id=5,
    )

    assert payload['machine_id'] == 12
    assert payload['machine_name'] == '1650#'
    assert payload['workshop_id'] == 18
    assert payload['confidence'] == 'high'


def test_resolves_online_annealing_north_line_with_wifi_suffix() -> None:
    machines = [
        _machine(machine_id=31, code='ZXTF-3', name='园区北', workshop_id=30, equipment_type='annealing_line'),
        _machine(machine_id=32, code='ZXTF-4', name='园区南', workshop_id=30, equipment_type='annealing_line'),
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        device_name='园区北线（WIFI）',
        process_hint='在线退火',
        preferred_workshop_id=30,
    )

    assert payload['machine_id'] == 31
    assert payload['machine_name'] == '园区北'
    assert payload['source'] == 'normalized_machine_name'


def test_keeps_generic_pc_terminal_unassigned() -> None:
    machines = [
        _machine(machine_id=41, code='JZ-ZJ-Z', name='纵剪', workshop_id=8, equipment_type='slitter'),
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        device_name='PC',
        process_hint='包装',
        preferred_workshop_id=8,
    )

    assert payload['machine_id'] is None
    assert payload['source'] == 'generic_mes_terminal'


def test_resolves_generic_pc_terminal_with_structured_binding() -> None:
    machines = [
        _machine(machine_id=41, code='JZ-ZJ-Z', name='纵剪', workshop_id=8, equipment_type='slitter'),
    ]
    bindings = [
        _terminal_binding(
            terminal_code='PC-JZ-01',
            equipment_id=41,
            workshop_name='精整',
            process_name='包装',
        )
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        terminal_bindings=bindings,
        terminal_hints={'DeviceCode': 'PC-JZ-01'},
        device_name='PC',
        process_hint='包装',
        workshop_name='精整',
        preferred_workshop_id=8,
    )

    assert payload['machine_id'] == 41
    assert payload['machine_name'] == '纵剪'
    assert payload['source'] == 'mes_terminal_binding'
    assert payload['confidence'] == 'high'


def test_resolves_terminal_binding_when_mes_machine_code_is_empty() -> None:
    machines = [
        _machine(machine_id=41, code='JZ-ZJ-Z', name='纵剪', workshop_id=8, equipment_type='slitter'),
    ]
    bindings = [
        _terminal_binding(
            terminal_code='PC-JZ-01',
            equipment_id=41,
            workshop_name='精整',
            process_name='包装',
        )
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        terminal_bindings=bindings,
        terminal_hints={'DeviceCode': 'PC-JZ-01'},
        device_name=None,
        process_hint='包装',
        workshop_name='精整',
        preferred_workshop_id=8,
    )

    assert payload['machine_id'] == 41
    assert payload['source'] == 'mes_terminal_binding'


def test_resolves_generic_pc_by_scoped_binding_without_terminal_hints() -> None:
    machines = [
        _machine(machine_id=41, code='JZ-BZJ', name='包装机', workshop_id=8, equipment_type='packaging_machine'),
        _machine(machine_id=51, code='LJ-BZJ', name='包装机', workshop_id=25, equipment_type='packaging_machine'),
    ]
    bindings = [
        _terminal_binding(
            terminal_code='PC',
            mes_device_name='PC',
            equipment_id=41,
            workshop_name='精整车间',
            process_name='包装',
        ),
        _terminal_binding(
            terminal_code='PC',
            mes_device_name='PC',
            equipment_id=51,
            workshop_name='拉矫车间',
            process_name='包装',
        ),
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        terminal_bindings=bindings,
        device_name='PC',
        process_hint='包装',
        workshop_name='精整车间',
        preferred_workshop_id=8,
    )

    assert payload['machine_id'] == 41
    assert payload['machine_name'] == '包装机'
    assert payload['source'] == 'mes_terminal_binding'


def test_does_not_apply_pc_terminal_binding_across_process_scope() -> None:
    machines = [
        _machine(machine_id=41, code='JZ-ZJ-Z', name='纵剪', workshop_id=8, equipment_type='slitter'),
    ]
    bindings = [
        _terminal_binding(
            terminal_code='PC-JZ-01',
            equipment_id=41,
            workshop_name='精整',
            process_name='包装',
        )
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        terminal_bindings=bindings,
        terminal_hints={'DeviceCode': 'PC-JZ-01'},
        device_name='PC',
        process_hint='冷轧',
        workshop_name='精整',
        preferred_workshop_id=8,
    )

    assert payload['machine_id'] is None
    assert payload['source'] == 'generic_mes_terminal'


def test_pc_terminal_binding_handles_timezone_aware_event_time() -> None:
    machines = [
        _machine(machine_id=41, code='JZ-ZJ-Z', name='纵剪', workshop_id=8, equipment_type='slitter'),
    ]
    bindings = [
        _terminal_binding(
            terminal_code='PC-JZ-01',
            equipment_id=41,
            workshop_name='精整',
            process_name='包装',
            valid_from=datetime(2026, 6, 10, 9, 30),
            valid_to=datetime(2026, 6, 11, 9, 30),
        )
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        terminal_bindings=bindings,
        terminal_hints={'DeviceCode': 'PC-JZ-01'},
        device_name='PC',
        process_hint='包装',
        workshop_name='精整',
        event_time=datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc),
    )

    assert payload['machine_id'] == 41
    assert payload['source'] == 'mes_terminal_binding'


def test_infers_north_annealing_line_from_route_when_machine_code_missing() -> None:
    machines = [
        _machine(machine_id=149, code='ZXTF-1', name='新厂北', workshop_id=29, equipment_type='annealing_line'),
        _machine(machine_id=150, code='ZXTF-2', name='新厂南', workshop_id=29, equipment_type='annealing_line'),
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        device_name=None,
        process_hint='北线退火',
        preferred_workshop_id=29,
    )

    assert payload['machine_id'] == 149
    assert payload['machine_name'] == '新厂北'
    assert payload['source'] == 'route_inferred'


def test_resolves_straightener_device_without_cross_matching_number_only_machines() -> None:
    machines = [
        _machine(machine_id=11, code='ZR2-3', name='3#机', workshop_id=2, equipment_type='cast_roller'),
        _machine(machine_id=12, code='JQ-3', name='3#', workshop_id=10, equipment_type='shear'),
        _machine(machine_id=41, code='JQ-LJ', name='拉矫', workshop_id=25, equipment_type='straightener'),
    ]

    payload = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        device_name='拉矫3号机（WAN）',
        process_hint='拉矫',
        preferred_workshop_id=25,
    )

    assert payload['machine_id'] == 41
    assert payload['machine_name'] == '拉矫'
    assert payload['source'] == 'contained_machine_name'
