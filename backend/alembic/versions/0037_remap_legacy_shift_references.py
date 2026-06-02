"""remap legacy shift references

Revision ID: 0037_remap_legacy_shift_references
Revises: 0036_unify_shift_configs
Create Date: 2026-06-02 19:40:00.000000
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from alembic import op


revision = '0037_remap_legacy_shift_references'
down_revision = '0036_unify_shift_configs'
branch_labels = None
depends_on = None


SHIFT_CODE_PAIRS = (('DAY', 'A'), ('MID', 'B'), ('NIGHT', 'C'))

SHIFT_REFERENCE_COLUMNS = (
    ('attendance_schedules', 'shift_config_id'),
    ('shift_attendance_confirmations', 'shift_id'),
    ('shift_swaps', 'original_shift_id'),
    ('shift_swaps', 'new_shift_id'),
    ('attendance_results', 'auto_shift_config_id'),
    ('attendance_results', 'shift_config_id'),
    ('attendance_exceptions', 'shift_config_id'),
    ('shift_production_data', 'shift_config_id'),
    ('production_exceptions', 'shift_config_id'),
    ('mobile_shift_reports', 'shift_config_id'),
    ('mobile_reminder_records', 'shift_config_id'),
    ('work_order_entries', 'shift_id'),
)

ASSIGNED_SHIFT_TABLES = ('users', 'equipment')


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not inspector.has_table(table_name):
        return False
    return any(item['name'] == column_name for item in inspector.get_columns(table_name))


def _shift_ids(conn: sa.Connection) -> dict[str, int]:
    rows = conn.execute(
        sa.text(
            """
            SELECT code, id
            FROM shift_configs
            WHERE code IN ('DAY', 'MID', 'NIGHT', 'A', 'B', 'C')
            """
        )
    ).mappings()
    return {str(row['code']).upper(): int(row['id']) for row in rows}


def _id_mapping(conn: sa.Connection, *, reverse: bool = False) -> dict[int, int]:
    ids = _shift_ids(conn)
    mapping: dict[int, int] = {}
    for old_code, new_code in SHIFT_CODE_PAIRS:
        source_code, target_code = (new_code, old_code) if reverse else (old_code, new_code)
        source_id = ids.get(source_code)
        target_id = ids.get(target_code)
        if source_id is not None and target_id is not None:
            mapping[source_id] = target_id
    return mapping


def _remap_scalar_references(
    conn: sa.Connection,
    inspector: sa.Inspector,
    mapping: dict[int, int],
) -> None:
    for table_name, column_name in SHIFT_REFERENCE_COLUMNS:
        if not _has_column(inspector, table_name, column_name):
            continue
        for source_id, target_id in mapping.items():
            conn.execute(
                sa.text(f'UPDATE {table_name} SET {column_name} = :target_id WHERE {column_name} = :source_id'),
                {'source_id': source_id, 'target_id': target_id},
            )


def _load_shift_list(raw_value: Any) -> list[Any] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw_value, list):
        return None
    return raw_value


def _remap_shift_list(raw_value: Any, mapping: dict[int, int]) -> list[int] | None:
    values = _load_shift_list(raw_value)
    if values is None:
        return None

    remapped: list[int] = []
    seen: set[int] = set()
    changed = False
    for value in values:
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            continue
        target_value = mapping.get(numeric_value, numeric_value)
        changed = changed or target_value != numeric_value
        if target_value in seen:
            changed = True
            continue
        seen.add(target_value)
        remapped.append(target_value)
    if not changed:
        return None
    return remapped


def _json_update_expression(conn: sa.Connection) -> str:
    if conn.dialect.name == 'postgresql':
        return 'CAST(:assigned_shift_ids AS jsonb)'
    return ':assigned_shift_ids'


def _remap_assigned_shift_lists(
    conn: sa.Connection,
    inspector: sa.Inspector,
    mapping: dict[int, int],
) -> None:
    json_expression = _json_update_expression(conn)
    for table_name in ASSIGNED_SHIFT_TABLES:
        if not _has_column(inspector, table_name, 'assigned_shift_ids'):
            continue
        rows = conn.execute(
            sa.text(f'SELECT id, assigned_shift_ids FROM {table_name} WHERE assigned_shift_ids IS NOT NULL')
        ).mappings()
        for row in rows:
            remapped = _remap_shift_list(row['assigned_shift_ids'], mapping)
            if remapped is None:
                continue
            conn.execute(
                sa.text(f'UPDATE {table_name} SET assigned_shift_ids = {json_expression} WHERE id = :row_id'),
                {'row_id': int(row['id']), 'assigned_shift_ids': json.dumps(remapped)},
            )


def _run_remap(*, reverse: bool = False) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table('shift_configs'):
        return
    mapping = _id_mapping(conn, reverse=reverse)
    if not mapping:
        return
    _remap_scalar_references(conn, inspector, mapping)
    _remap_assigned_shift_lists(conn, inspector, mapping)


def upgrade() -> None:
    _run_remap(reverse=False)


def downgrade() -> None:
    _run_remap(reverse=True)
