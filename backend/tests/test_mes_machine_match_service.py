from __future__ import annotations

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
