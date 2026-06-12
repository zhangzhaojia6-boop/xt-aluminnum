"""Safe IoT energy connectivity preflight.

This command is read-only and never prints credentials. It checks whether the
external IoT energy source can return sample meter readings and whether those
meter codes are mapped to local workshops/machines.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.iot_energy_adapter import IotEnergyAdapter
from app.config import Settings, settings
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.services.iot_energy_sync_service import get_iot_energy_adapter_for_settings


AdapterFactory = Callable[[Settings], IotEnergyAdapter | None]


def _configured(runtime: Settings) -> bool:
    return (runtime.IOT_ENERGY_ADAPTER or 'null').strip().lower() != 'null'


def _sqlserver_missing_env(runtime: Settings) -> list[str]:
    missing: list[str] = []
    checks = (
        ('IOT_ENERGY_SQLSERVER_HOST', runtime.IOT_ENERGY_SQLSERVER_HOST),
        ('IOT_ENERGY_SQLSERVER_DATABASE', runtime.IOT_ENERGY_SQLSERVER_DATABASE),
        ('IOT_ENERGY_SQLSERVER_USERNAME', runtime.IOT_ENERGY_SQLSERVER_USERNAME),
        ('IOT_ENERGY_SQLSERVER_PASSWORD', runtime.IOT_ENERGY_SQLSERVER_PASSWORD),
        ('IOT_ENERGY_SQLSERVER_QUERY', runtime.IOT_ENERGY_SQLSERVER_QUERY),
    )
    for name, value in checks:
        if not str(value or '').strip():
            missing.append(name)
    if not runtime.iot_energy_meter_map:
        missing.append('IOT_ENERGY_METER_MAP')
    return missing


def _readiness_payload(
    *,
    configured: bool,
    required_env: list[str] | None = None,
    readings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    required = list(required_env or [])
    next_actions: list[str] = []
    if not configured:
        next_actions.append('配置物联网能耗只读连接')
    if any(name.startswith('IOT_ENERGY_SQLSERVER_') for name in required):
        next_actions.append('补齐物联网数据库地址、库名、只读账号和查询 SQL')
    if 'IOT_ENERGY_METER_MAP' in required:
        next_actions.append('补齐表计/点位到车间、机列的映射')

    missing_meters = list((readings or {}).get('meters_missing_mapping') or [])
    if missing_meters:
        next_actions.append(f"补齐未映射表计：{', '.join(missing_meters)}")
    if readings is not None and readings.get('count') == 0 and configured and not required:
        next_actions.append('确认物联网查询 SQL 的时间范围能返回当日读数')

    return {
        'ready': configured and not required and readings is not None and readings.get('count', 0) > 0 and not missing_meters,
        'required_env': required,
        'next_actions': next_actions,
    }


def _normalize_code(value: Any) -> str:
    return str(value or '').strip().upper()


def _round(value: float) -> float:
    return round(float(value), 4)


def _reading_payload(reading: Any, mapping: dict[str, str]) -> dict[str, Any]:
    meter_code = str(reading.meter_code).strip()
    return {
        'meter_code': meter_code,
        'meter_name': reading.meter_name,
        'reading_at': reading.reading_at.isoformat() if reading.reading_at else None,
        'electricity_kwh': reading.electricity_kwh,
        'gas_m3': reading.gas_m3,
        'water_m3': reading.water_m3,
        'mapping_status': 'mapped' if mapping else 'missing_mapping',
        'mapping': dict(mapping),
        'metadata': filter_sensitive_mapping(reading.metadata or {}),
    }


def _summarize_readings(readings: list[Any], meter_map: dict[str, dict[str, str]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    meter_codes: set[str] = set()
    missing_mapping: list[str] = []
    electricity_total = 0.0
    gas_total = 0.0
    water_total = 0.0

    for reading in readings:
        meter_code = str(reading.meter_code).strip()
        normalized_code = _normalize_code(meter_code)
        if not meter_code:
            continue
        mapping = meter_map.get(normalized_code, {})
        meter_codes.add(meter_code)
        if not mapping:
            missing_mapping.append(meter_code)
        if reading.electricity_kwh is not None:
            electricity_total += float(reading.electricity_kwh)
        if reading.gas_m3 is not None:
            gas_total += float(reading.gas_m3)
        if reading.water_m3 is not None:
            water_total += float(reading.water_m3)
        items.append(_reading_payload(reading, dict(mapping)))

    return {
        'count': len(items),
        'meter_count': len(meter_codes),
        'meters_with_mapping': len(meter_codes) - len(set(missing_mapping)),
        'meters_missing_mapping': sorted(set(missing_mapping)),
        'totals': {
            'electricity_kwh': _round(electricity_total),
            'gas_m3': _round(gas_total),
            'water_m3': _round(water_total),
        },
        'items': items[:50],
    }


def inspect_iot_energy_preflight(
    *,
    runtime_settings: Settings | None = None,
    adapter_factory: AdapterFactory | None = None,
    target_date: date | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    runtime = runtime_settings or settings
    adapter_name = (runtime.IOT_ENERGY_ADAPTER or 'null').strip().lower()
    business_date = target_date or date.today()
    payload: dict[str, Any] = {
        'adapter': adapter_name,
        'configured': _configured(runtime),
        'business_date': business_date.isoformat(),
        'connection': {'status': 'skipped'},
        'readings': {
            'count': 0,
            'meter_count': 0,
            'meters_with_mapping': 0,
            'meters_missing_mapping': [],
            'totals': {'electricity_kwh': 0.0, 'gas_m3': 0.0, 'water_m3': 0.0},
            'items': [],
        },
    }
    payload['readiness'] = _readiness_payload(configured=payload['configured'], readings=payload['readings'])
    if not payload['configured']:
        payload['connection']['reason'] = 'missing_config'
        payload['readiness'] = _readiness_payload(
            configured=False,
            required_env=['IOT_ENERGY_ADAPTER'],
            readings=payload['readings'],
        )
        return payload

    if adapter_name == 'sqlserver':
        missing_env = _sqlserver_missing_env(runtime)
        if missing_env:
            payload['connection']['reason'] = 'missing_sqlserver_config'
            payload['readiness'] = _readiness_payload(
                configured=True,
                required_env=missing_env,
                readings=payload['readings'],
            )
            return payload

    try:
        factory = adapter_factory or get_iot_energy_adapter_for_settings
        adapter = factory(runtime)
        if adapter is None:
            payload['configured'] = False
            payload['connection']['reason'] = 'missing_config'
            payload['readiness'] = _readiness_payload(
                configured=False,
                required_env=['IOT_ENERGY_ADAPTER'],
                readings=payload['readings'],
            )
            return payload
        readings = adapter.list_readings(business_date=business_date, limit=limit)
    except Exception as exc:  # noqa: BLE001 - diagnostic command reports class and redacted message
        payload['connection'] = {
            'status': 'failed',
            'error': exc.__class__.__name__,
            'message': redact_secret_text(str(exc)),
        }
        payload['readiness'] = _readiness_payload(configured=True, readings=payload['readings'])
        return payload

    meter_map = {
        _normalize_code(key): dict(value)
        for key, value in runtime.iot_energy_meter_map.items()
        if _normalize_code(key)
    }
    payload['connection'] = {'status': 'success'}
    payload['readings'] = _summarize_readings(list(readings), meter_map)
    payload['readiness'] = _readiness_payload(configured=True, readings=payload['readings'])
    return payload


def _print_text(payload: dict[str, Any]) -> None:
    print(f"IoT energy adapter: {payload['adapter']}")
    print(f"Configured: {str(payload['configured']).lower()}")
    print(f"Business date: {payload['business_date']}")
    print(f"Connection: {payload['connection']['status']}")
    if payload['connection'].get('reason'):
        print(f"Connection reason: {payload['connection']['reason']}")
    if payload['connection'].get('error'):
        print(f"Connection error: {payload['connection']['error']}")
    readings = payload['readings']
    print(f"Readings: {readings['count']}")
    print(f"Mapped meters: {readings['meters_with_mapping']}")
    if readings['meters_missing_mapping']:
        print(f"Missing meter mappings: {', '.join(readings['meters_missing_mapping'])}")
    totals = readings['totals']
    print(
        "Totals: "
        f"{totals['electricity_kwh']} kWh, "
        f"{totals['gas_m3']} m3 gas, "
        f"{totals['water_m3']} m3 water"
    )
    readiness = payload.get('readiness') or {}
    print(f"Ready: {str(readiness.get('ready', False)).lower()}")
    if readiness.get('required_env'):
        print(f"Required env: {', '.join(readiness['required_env'])}")
    if readiness.get('next_actions'):
        print(f"Next actions: {'; '.join(readiness['next_actions'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check IoT energy source without writing local shadow tables.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    parser.add_argument('--business-date', default='', help='Business date in YYYY-MM-DD. Default: today.')
    parser.add_argument('--limit', type=int, default=50, help='Maximum sample readings to inspect.')
    args = parser.parse_args(argv)

    target_date = date.fromisoformat(args.business_date) if args.business_date else None
    payload = inspect_iot_energy_preflight(target_date=target_date, limit=args.limit)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_text(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
