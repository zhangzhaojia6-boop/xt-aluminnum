"""Safe MES SQL Server connectivity preflight.

This command is read-only and never prints credentials. It inspects only
connection status plus table/column metadata so field mapping can be planned
before business data is imported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.sqlserver_mes_adapter import _run_pymssql_query, inspect_sqlserver_metadata
from app.config import Settings, settings
from app.core.redaction import is_sensitive_key


_FIELD_RULES: dict[str, tuple[str, ...]] = {
    'tracking_card_no': ('trackingcardno', 'trackingcardnumber', 'followcardno', 'flowcardno', 'cardno', 'materialcode'),
    'customer_name': ('customername', 'clientname', 'custname'),
    'alloy_grade': ('alloygrade', 'alloy'),
    'spec': ('spec', 'specification'),
    'current_workshop': ('currentworkshop', 'currentworkshopname', 'workshopname', 'currentworkshop'),
    'current_process': ('currentprocess', 'currentprocessname', 'processname'),
    'next_workshop': ('nextworkshop', 'nextworkshopname'),
    'next_process': ('nextprocess', 'nextprocessname'),
    'process_route': ('processroute', 'printprocessroute', 'route'),
    'input_weight': ('inputweight', 'feedingweight', 'feedweight'),
    'output_weight': ('outputweight', 'finishweight', 'productionweight'),
    'stock_in_weight': ('stockinweight', 'instockweight', 'warehouseweight'),
    'scrap_weight': ('scrapweight', 'wasteweight'),
}


_ROLE_RULES: dict[str, tuple[str, ...]] = {
    'coil_status': ('coilstatus', 'followcard', 'dispatch', 'productstatus'),
    'process_route': ('processroute', 'route'),
    'wip_total': ('wip', 'doing', 'workinprocess'),
    'stock_in': ('stockin', 'warehouse', 'inventory'),
    'material': ('material', 'feeding'),
    'yield': ('yield', 'production'),
    'device': ('device', 'machine', 'line'),
}


def _is_blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _missing_sqlserver_env(runtime: Settings) -> list[str]:
    missing: list[str] = []
    adapter = (runtime.MES_ADAPTER or 'null').strip().lower()
    if adapter != 'sqlserver':
        missing.append('MES_ADAPTER')
    for name in ('MES_SQLSERVER_HOST', 'MES_SQLSERVER_DATABASE', 'MES_SQLSERVER_USERNAME', 'MES_SQLSERVER_PASSWORD'):
        if _is_blank(getattr(runtime, name)):
            missing.append(name)
    return missing


def _compact(value: str) -> str:
    return ''.join(ch for ch in value.lower() if ch.isalnum())


def _column_names(table: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for column in table.get('columns') or []:
        if not isinstance(column, dict):
            continue
        name = str(column.get('name') or '').strip()
        if name:
            names.append(name)
    return names


def _safe_metadata_tables(tables: list[Any]) -> list[dict[str, Any]]:
    safe_tables: list[dict[str, Any]] = []
    for table in tables:
        if not isinstance(table, dict):
            continue
        safe_table = dict(table)
        safe_columns: list[dict[str, Any]] = []
        for column in table.get('columns') or []:
            if not isinstance(column, dict):
                continue
            name = str(column.get('name') or '').strip()
            if not name or is_sensitive_key(name):
                continue
            safe_columns.append({
                'name': name,
                'data_type': column.get('data_type'),
            })
        safe_table['columns'] = safe_columns
        safe_tables.append(safe_table)
    return safe_tables


def _matches_any(column_name: str, tokens: tuple[str, ...]) -> bool:
    compact = _compact(column_name)
    return any(token in compact for token in tokens)


def _business_roles(table_name: str) -> list[str]:
    compact = _compact(table_name)
    return [role for role, tokens in _ROLE_RULES.items() if any(token in compact for token in tokens)]


def build_field_map(metadata: dict[str, Any]) -> dict[str, Any]:
    table_items: list[dict[str, Any]] = []
    for table in metadata.get('tables') or []:
        if not isinstance(table, dict):
            continue
        table_name = str(table.get('name') or '').strip()
        columns = _column_names(table)
        safe_columns = [column for column in columns if not is_sensitive_key(column)]
        field_matches = {
            target: [column for column in safe_columns if _matches_any(column, tokens)]
            for target, tokens in _FIELD_RULES.items()
        }
        field_matches = {target: matches for target, matches in field_matches.items() if matches}
        table_items.append({
            'schema': table.get('schema'),
            'name': table_name,
            'business_roles': _business_roles(table_name),
            'primary_key_candidates': [
                column for column in safe_columns if _compact(column) in {'id', 'productid', 'sourceid', 'recordid'}
            ],
            'updated_at_candidates': [
                column for column in safe_columns if _matches_any(column, ('updatetime', 'updatedat', 'modifytime', 'modifiedat'))
            ],
            'time_field_candidates': [
                column for column in safe_columns if _matches_any(column, ('time', 'date', 'datetime'))
            ],
            'status_field_candidates': [
                column for column in safe_columns if _matches_any(column, ('status', 'state'))
            ],
            'weight_field_candidates': [
                column for column in safe_columns if _matches_any(column, ('weight', 'tons', 'ton', 'kg'))
            ],
            'field_matches': field_matches,
        })
    return {
        'database_name': metadata.get('database_name'),
        'tables': table_items,
    }


def _probe(runtime: Settings) -> dict[str, Any]:
    return inspect_sqlserver_metadata(
        host=str(runtime.MES_SQLSERVER_HOST or '').strip(),
        port=int(runtime.MES_SQLSERVER_PORT),
        database=str(runtime.MES_SQLSERVER_DATABASE or '').strip(),
        username=str(runtime.MES_SQLSERVER_USERNAME or '').strip(),
        password=str(runtime.MES_SQLSERVER_PASSWORD or ''),
        timeout_seconds=runtime.MES_SQLSERVER_TIMEOUT_SECONDS,
        encrypt=runtime.MES_SQLSERVER_ENCRYPT,
    )


def _permission_probe(runtime: Settings) -> dict[str, Any]:
    rows = _run_pymssql_query(
        host=str(runtime.MES_SQLSERVER_HOST or '').strip(),
        port=int(runtime.MES_SQLSERVER_PORT),
        database=str(runtime.MES_SQLSERVER_DATABASE or '').strip(),
        username=str(runtime.MES_SQLSERVER_USERNAME or '').strip(),
        password=str(runtime.MES_SQLSERVER_PASSWORD or ''),
        timeout_seconds=runtime.MES_SQLSERVER_TIMEOUT_SECONDS,
        encrypt=runtime.MES_SQLSERVER_ENCRYPT,
        query=(
            "SELECT DB_NAME() AS database_name, "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'SELECT') AS can_select, "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT') AS can_insert, "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE') AS can_update, "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE') AS can_delete, "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE') AS can_create_table, "
            "IS_SRVROLEMEMBER('sysadmin') AS is_sysadmin, "
            "IS_SRVROLEMEMBER('dbcreator') AS is_dbcreator"
        ),
    )
    return dict(rows[0]) if rows else {}


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes'}


def _permission_payload(raw: dict[str, Any]) -> dict[str, Any]:
    can_select = _boolish(raw.get('can_select'))
    can_insert = _boolish(raw.get('can_insert'))
    can_update = _boolish(raw.get('can_update'))
    can_delete = _boolish(raw.get('can_delete'))
    can_create_table = _boolish(raw.get('can_create_table'))
    is_sysadmin = _boolish(raw.get('is_sysadmin'))
    is_dbcreator = _boolish(raw.get('is_dbcreator'))
    return {
        'status': 'success',
        'database_name': raw.get('database_name'),
        'can_select': can_select,
        'can_insert': can_insert,
        'can_update': can_update,
        'can_delete': can_delete,
        'can_create_table': can_create_table,
        'is_sysadmin': is_sysadmin,
        'is_dbcreator': is_dbcreator,
        'read_only_account': (
            can_select
            and not can_insert
            and not can_update
            and not can_delete
            and not can_create_table
            and not is_sysadmin
            and not is_dbcreator
        ),
    }


def inspect_mes_sqlserver_preflight(
    *,
    runtime_settings: Settings | None = None,
    probe=None,
    permission_probe=None,
) -> dict[str, Any]:
    runtime = runtime_settings or settings
    adapter_name = (runtime.MES_ADAPTER or 'null').strip().lower()
    missing_env = _missing_sqlserver_env(runtime)
    payload: dict[str, Any] = {
        'adapter': adapter_name,
        'sqlserver_configured': not missing_env,
        'missing_env': missing_env,
        'connection': {'status': 'skipped'},
        'database': {'name': None},
        'tables': {'count': 0, 'items': []},
        'field_map': {'database_name': None, 'tables': []},
        'permissions': {'status': 'skipped'},
    }
    if missing_env:
        payload['connection']['reason'] = 'missing_config'
        return payload

    metadata_probe = probe or _probe
    try:
        metadata = metadata_probe(runtime)
    except Exception as exc:  # noqa: BLE001 - diagnostic command reports class only
        payload['connection'] = {
            'status': 'failed',
            'error': exc.__class__.__name__,
        }
        return payload

    tables = _safe_metadata_tables(list(metadata.get('tables') or []))
    payload['connection'] = {'status': 'success'}
    payload['database'] = {'name': metadata.get('database_name')}
    payload['tables'] = {'count': len(tables), 'items': tables}
    payload['field_map'] = build_field_map(metadata)
    permission_reader = permission_probe or _permission_probe
    try:
        payload['permissions'] = _permission_payload(permission_reader(runtime))
    except Exception as exc:  # noqa: BLE001 - diagnostic command reports class only
        payload['permissions'] = {
            'status': 'failed',
            'error': exc.__class__.__name__,
        }
    return payload


def _print_text(payload: dict[str, Any]) -> None:
    print(f"MES SQL Server adapter: {payload['adapter']}")
    print(f"SQL Server configured: {str(payload['sqlserver_configured']).lower()}")
    if payload['missing_env']:
        print(f"Missing env: {', '.join(payload['missing_env'])}")
    print(f"Connection: {payload['connection']['status']}")
    if payload['connection'].get('reason'):
        print(f"Connection reason: {payload['connection']['reason']}")
    if payload['connection'].get('error'):
        print(f"Connection error: {payload['connection']['error']}")
    if payload['database'].get('name'):
        print(f"Database: {payload['database']['name']}")
    print(f"Permission probe: {payload['permissions']['status']}")
    if payload['permissions'].get('read_only_account') is not None:
        print(f"Read-only account: {str(payload['permissions']['read_only_account']).lower()}")
    print(f"Tables/views discovered: {payload['tables']['count']}")
    for item in payload['tables']['items'][:10]:
        columns = ', '.join(column.get('name', '') for column in item.get('columns', [])[:8] if column.get('name'))
        print(f"- {item.get('schema')}.{item.get('name')}: {columns}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check MES SQL Server connectivity without printing secrets.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args(argv)

    payload = inspect_mes_sqlserver_preflight()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
