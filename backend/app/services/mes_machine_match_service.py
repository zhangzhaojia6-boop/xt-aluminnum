from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable, Mapping

from app.models.master import Equipment, MasterCodeAlias, MesTerminalBinding
from app.services.real_master_data import VIRTUAL_QR_EQUIPMENT_TYPES


GENERIC_MES_DEVICE_NAMES = {'PC', '电脑', '一体机'}

TERMINAL_HINT_KEYS = (
    'DeviceCode',
    'MachineCode',
    'WorkShopLine',
    'LineName',
    'TerminalCode',
    'TerminalName',
    'StationCode',
    'StationName',
    'ClientName',
    'ComputerName',
    'HostName',
    'IPAddress',
    'ClientIp',
    'IP',
    'Ip',
)

MES_PROCESS_MACHINE_TYPE_HINTS = (
    (('冷轧',), {'cold_mill'}),
    (('北线退火', '南线退火', '在线退火', '退火'), {'annealing_line'}),
    (('纵剪', '分切'), {'slitter'}),
    (('重卷',), {'recoiler'}),
    (('拉矫', '洗拉'), {'straightener'}),
    (('横剪',), {'cross_cut'}),
    (('飞剪',), {'fly_cut'}),
    (('剪切',), {'shear', 'cross_cut', 'fly_cut'}),
    (('铣',), {'milling'}),
    (('锯',), {'sawing'}),
    (('热轧',), {'hot_mill'}),
)


def _text(value: Any) -> str:
    return str(value or '').strip()


def normalize_mes_machine_text(value: Any) -> str:
    text = _text(value).upper()
    if not text:
        return ''
    text = text.replace('＃', '#').replace(' ', '')
    text = re.sub(r'[（(]\s*(WAN|WIFI|WI-FI|无线|有线)\s*[）)]', '', text, flags=re.IGNORECASE)
    text = text.replace('号机', '#').replace('号', '#')
    text = text.replace('＃', '#')
    return text.strip()


def _text_forms(value: Any) -> set[str]:
    normalized = normalize_mes_machine_text(value)
    if not normalized:
        return set()
    forms = {normalized}
    if normalized.endswith('线'):
        forms.add(normalized[:-1])
    if normalized.endswith('机'):
        forms.add(normalized[:-1])
    forms.add(normalized.replace('#', ''))
    return {item for item in forms if item}


def _is_generic_device(value: Any) -> bool:
    normalized = normalize_mes_machine_text(value)
    return normalized in GENERIC_MES_DEVICE_NAMES


def is_physical_machine(machine: Equipment) -> bool:
    equipment_type = _text(getattr(machine, 'equipment_type', '')).lower()
    return equipment_type not in VIRTUAL_QR_EQUIPMENT_TYPES


def _machine_payload(machine: Equipment, *, source: str, confidence: str, raw_device_name: Any) -> dict[str, Any]:
    return {
        'machine_id': getattr(machine, 'id', None),
        'machine_code': getattr(machine, 'code', None),
        'machine_name': getattr(machine, 'name', None),
        'workshop_id': getattr(machine, 'workshop_id', None),
        'source': source,
        'confidence': confidence,
        'raw_device_name': _text(raw_device_name) or None,
    }


def _terminal_hint_forms(terminal_hints: Mapping[str, Any] | None) -> set[str]:
    if not terminal_hints:
        return set()
    forms: set[str] = set()
    for key in TERMINAL_HINT_KEYS:
        forms.update(_text_forms(terminal_hints.get(key)))
    return forms


def _binding_forms(binding: MesTerminalBinding) -> set[str]:
    forms = set()
    forms.update(_text_forms(getattr(binding, 'terminal_code', None)))
    forms.update(_text_forms(getattr(binding, 'terminal_name', None)))
    forms.update(_text_forms(getattr(binding, 'mes_device_name', None)))
    return forms


def _empty_payload(*, source: str, raw_device_name: Any) -> dict[str, Any]:
    return {
        'machine_id': None,
        'machine_code': None,
        'machine_name': None,
        'workshop_id': None,
        'source': source,
        'confidence': 'low',
        'raw_device_name': _text(raw_device_name) or None,
    }


def _machine_forms(machine: Equipment) -> set[str]:
    forms = set()
    forms.update(_text_forms(getattr(machine, 'code', None)))
    forms.update(_text_forms(getattr(machine, 'name', None)))
    return forms


def _is_weak_machine_form(value: str) -> bool:
    return bool(re.fullmatch(r'\d{1,2}(#|机|线)?', value))


def _unique(candidates: Iterable[Equipment]) -> Equipment | None:
    rows: list[Equipment] = []
    seen: set[object] = set()
    for candidate in candidates:
        key = getattr(candidate, 'id', None)
        if key is None:
            key = id(candidate)
        if key in seen:
            continue
        seen.add(key)
        rows.append(candidate)
    return rows[0] if len(rows) == 1 else None


def _match_alias(
    *,
    machines: list[Equipment],
    aliases: Iterable[MasterCodeAlias],
    device_forms: set[str],
) -> Equipment | None:
    if not device_forms:
        return None
    machine_by_code = {_text(getattr(machine, 'code', '')).upper(): machine for machine in machines}
    for alias in aliases:
        alias_forms = _text_forms(getattr(alias, 'alias_code', None)) | _text_forms(getattr(alias, 'alias_name', None))
        if not (alias_forms & device_forms):
            continue
        machine = machine_by_code.get(_text(getattr(alias, 'canonical_code', '')).upper())
        if machine is not None:
            return machine
    return None


def _match_direct_code(*, machines: list[Equipment], device_forms: set[str]) -> Equipment | None:
    return _unique(
        machine
        for machine in machines
        if _text(getattr(machine, 'code', '')).upper() in device_forms
    )


def _match_normalized_name(*, machines: list[Equipment], device_forms: set[str]) -> Equipment | None:
    return _unique(
        machine
        for machine in machines
        if _text_forms(getattr(machine, 'name', None)) & device_forms
    )


def _match_contained_name(*, machines: list[Equipment], device_forms: set[str]) -> Equipment | None:
    candidates: list[Equipment] = []
    for machine in machines:
        forms = {form for form in _machine_forms(machine) if not _is_weak_machine_form(form)}
        if any(
            (machine_form in device_form and len(machine_form) >= 2)
            or (device_form in machine_form and len(device_form) >= 3)
            for machine_form in forms
            for device_form in device_forms
        ):
            candidates.append(machine)
    return _unique(candidates)


def _match_numeric_hint(*, machines: list[Equipment], device_forms: set[str]) -> Equipment | None:
    tokens = {
        token
        for form in device_forms
        for token in re.findall(r'\d{3,4}', form)
    }
    if not tokens:
        return None
    candidates = [
        machine
        for machine in machines
        if any(token in form for token in tokens for form in _machine_forms(machine))
    ]
    return _unique(candidates)


def _binding_in_effect(binding: MesTerminalBinding, event_time: datetime | None) -> bool:
    if not getattr(binding, 'is_active', True):
        return False
    if event_time is None:
        return True
    event_at = event_time.replace(tzinfo=None) if event_time.tzinfo is not None else event_time
    valid_from = getattr(binding, 'valid_from', None)
    valid_to = getattr(binding, 'valid_to', None)
    if valid_from is not None and valid_from.tzinfo is not None:
        valid_from = valid_from.replace(tzinfo=None)
    if valid_to is not None and valid_to.tzinfo is not None:
        valid_to = valid_to.replace(tzinfo=None)
    if valid_from is not None and event_at < valid_from:
        return False
    if valid_to is not None and event_at >= valid_to:
        return False
    return True


def _matches_scope(binding_value: Any, actual_value: Any) -> bool:
    expected = normalize_mes_machine_text(binding_value)
    if not expected:
        return True
    actual = normalize_mes_machine_text(actual_value)
    return expected == actual


def _match_terminal_binding(
    *,
    machines: list[Equipment],
    terminal_bindings: Iterable[MesTerminalBinding],
    terminal_hints: Mapping[str, Any] | None,
    workshop_name: object | None,
    process_hint: object | None,
    event_time: datetime | None,
) -> tuple[Equipment, MesTerminalBinding] | None:
    hint_forms = _terminal_hint_forms(terminal_hints)
    if not hint_forms:
        return None
    machine_by_id = {getattr(machine, 'id', None): machine for machine in machines}
    for binding in terminal_bindings:
        if not _binding_in_effect(binding, event_time):
            continue
        if not _matches_scope(getattr(binding, 'workshop_name', None), workshop_name):
            continue
        if not _matches_scope(getattr(binding, 'process_name', None), process_hint):
            continue
        if not (_binding_forms(binding) & hint_forms):
            continue
        machine = machine_by_id.get(getattr(binding, 'equipment_id', None))
        if machine is not None and is_physical_machine(machine):
            return machine, binding
    return None


def _match_scoped_generic_device_binding(
    *,
    machines: list[Equipment],
    terminal_bindings: Iterable[MesTerminalBinding],
    device_name: object | None,
    workshop_name: object | None,
    process_hint: object | None,
    event_time: datetime | None,
) -> tuple[Equipment, MesTerminalBinding] | None:
    device_forms = _text_forms(device_name)
    if not device_forms or not _is_generic_device(device_name):
        return None
    machine_by_id = {getattr(machine, 'id', None): machine for machine in machines}
    matches: list[tuple[Equipment, MesTerminalBinding]] = []
    seen_equipment_ids: set[int] = set()
    for binding in terminal_bindings:
        if not _binding_in_effect(binding, event_time):
            continue
        if not _matches_scope(getattr(binding, 'workshop_name', None), workshop_name):
            continue
        if not _matches_scope(getattr(binding, 'process_name', None), process_hint):
            continue
        if not (_binding_forms(binding) & device_forms):
            continue
        machine = machine_by_id.get(getattr(binding, 'equipment_id', None))
        if machine is not None and is_physical_machine(machine):
            matches.append((machine, binding))
            if getattr(machine, 'id', None) is not None:
                seen_equipment_ids.add(int(machine.id))
    if len(matches) == 1 or len(seen_equipment_ids) == 1:
        return matches[0]
    return None


def infer_mes_machine_id_from_route(*, machines: list[Equipment], process_hint: object | None) -> int | None:
    physical_machines = [machine for machine in machines if is_physical_machine(machine)]
    if len(physical_machines) == 1:
        return physical_machines[0].id

    process_text = _text(process_hint)
    if not process_text:
        return None

    for keywords, equipment_types in MES_PROCESS_MACHINE_TYPE_HINTS:
        if not any(keyword in process_text for keyword in keywords):
            continue
        matches = [
            machine
            for machine in physical_machines
            if _text(getattr(machine, 'equipment_type', '')).lower() in equipment_types
        ]
        directional = _match_directional_route_hint(machines=matches, process_hint=process_text)
        if directional is not None:
            return directional.id
        if len(matches) == 1:
            return matches[0].id
        return None
    return None


def _match_directional_route_hint(*, machines: list[Equipment], process_hint: str) -> Equipment | None:
    direction_markers: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (('北', 'north'), ('北', 'NORTH', 'N线', 'N#', '-N', '_N')),
        (('南', 'south'), ('南', 'SOUTH', 'S线', 'S#', '-S', '_S')),
    )
    for hint_markers, machine_markers in direction_markers:
        if not any(marker in process_hint for marker in hint_markers):
            continue
        return _unique(
            machine
            for machine in machines
            if any(
                marker in normalize_mes_machine_text(getattr(machine, field, None))
                for field in ('code', 'name')
                for marker in machine_markers
            )
        )
    return None


def _scoped_machines(
    *,
    machines: list[Equipment],
    preferred_workshop_id: int | None,
) -> list[list[Equipment]]:
    physical = [machine for machine in machines if is_physical_machine(machine)]
    if preferred_workshop_id is None:
        return [physical]
    preferred = [machine for machine in physical if getattr(machine, 'workshop_id', None) == preferred_workshop_id]
    return [preferred, physical] if preferred and len(preferred) != len(physical) else [physical]


def resolve_mes_machine_binding(
    *,
    machines: list[Equipment],
    device_name: object | None,
    process_hint: object | None = None,
    preferred_workshop_id: int | None = None,
    aliases: Iterable[MasterCodeAlias] = (),
    terminal_bindings: Iterable[MesTerminalBinding] = (),
    terminal_hints: Mapping[str, Any] | None = None,
    workshop_name: object | None = None,
    event_time: datetime | None = None,
) -> dict[str, Any]:
    device_forms = _text_forms(device_name)
    if not device_forms:
        terminal_match = _match_terminal_binding(
            machines=machines,
            terminal_bindings=terminal_bindings,
            terminal_hints=terminal_hints,
            workshop_name=workshop_name,
            process_hint=process_hint,
            event_time=event_time,
        )
        if terminal_match is not None:
            machine, binding = terminal_match
            return _machine_payload(
                machine,
                source='mes_terminal_binding',
                confidence=_text(getattr(binding, 'confidence', None)) or 'high',
                raw_device_name=device_name,
            )
    if _is_generic_device(device_name):
        terminal_match = _match_terminal_binding(
            machines=machines,
            terminal_bindings=terminal_bindings,
            terminal_hints=terminal_hints,
            workshop_name=workshop_name,
            process_hint=process_hint,
            event_time=event_time,
        )
        if terminal_match is not None:
            machine, binding = terminal_match
            return _machine_payload(
                machine,
                source='mes_terminal_binding',
                confidence=_text(getattr(binding, 'confidence', None)) or 'high',
                raw_device_name=device_name,
            )
        scoped_match = _match_scoped_generic_device_binding(
            machines=machines,
            terminal_bindings=terminal_bindings,
            device_name=device_name,
            workshop_name=workshop_name,
            process_hint=process_hint,
            event_time=event_time,
        )
        if scoped_match is not None:
            machine, binding = scoped_match
            return _machine_payload(
                machine,
                source='mes_terminal_binding',
                confidence=_text(getattr(binding, 'confidence', None)) or 'high',
                raw_device_name=device_name,
            )
        return _empty_payload(source='generic_mes_terminal', raw_device_name=device_name)

    for scoped in _scoped_machines(machines=machines, preferred_workshop_id=preferred_workshop_id):
        alias_match = _match_alias(machines=scoped, aliases=aliases, device_forms=device_forms)
        if alias_match is not None:
            return _machine_payload(alias_match, source='equipment_alias', confidence='high', raw_device_name=device_name)

        code_match = _match_direct_code(machines=scoped, device_forms=device_forms)
        if code_match is not None:
            return _machine_payload(code_match, source='direct_machine_code', confidence='high', raw_device_name=device_name)

        name_match = _match_normalized_name(machines=scoped, device_forms=device_forms)
        if name_match is not None:
            return _machine_payload(name_match, source='normalized_machine_name', confidence='high', raw_device_name=device_name)

        contained_match = _match_contained_name(machines=scoped, device_forms=device_forms)
        if contained_match is not None:
            return _machine_payload(contained_match, source='contained_machine_name', confidence='high', raw_device_name=device_name)

        numeric_match = _match_numeric_hint(machines=scoped, device_forms=device_forms)
        if numeric_match is not None:
            return _machine_payload(numeric_match, source='numeric_machine_hint', confidence='high', raw_device_name=device_name)

    for scoped in _scoped_machines(machines=machines, preferred_workshop_id=preferred_workshop_id):
        inferred_id = infer_mes_machine_id_from_route(machines=scoped, process_hint=process_hint)
        if inferred_id is None:
            continue
        inferred = next((machine for machine in scoped if getattr(machine, 'id', None) == inferred_id), None)
        if inferred is not None:
            return _machine_payload(inferred, source='route_inferred', confidence='medium', raw_device_name=device_name)

    return _empty_payload(source='unresolved', raw_device_name=device_name)
