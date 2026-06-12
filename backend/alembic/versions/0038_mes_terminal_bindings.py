"""mes terminal bindings

Revision ID: 0038_mes_terminal_bindings
Revises: 0037_remap_legacy_shift_references
Create Date: 2026-06-11 16:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0038_mes_terminal_bindings'
down_revision = '0037_remap_legacy_shift_references'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'mes_terminal_bindings'):
        return

    op.create_table(
        'mes_terminal_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('terminal_code', sa.String(128), nullable=False),
        sa.Column('terminal_name', sa.String(128), nullable=True),
        sa.Column('mes_device_name', sa.String(128), nullable=True),
        sa.Column('workshop_name', sa.String(128), nullable=True),
        sa.Column('process_name', sa.String(128), nullable=True),
        sa.Column('equipment_id', sa.Integer(), sa.ForeignKey('equipment.id'), nullable=False),
        sa.Column('confidence', sa.String(16), nullable=False, server_default='high'),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_to', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            'terminal_code',
            'workshop_name',
            'process_name',
            'valid_from',
            name='uq_mes_terminal_binding_scope',
        ),
    )
    for column in ('terminal_code', 'mes_device_name', 'workshop_name', 'process_name', 'equipment_id'):
        op.create_index(f'ix_mes_terminal_bindings_{column}', 'mes_terminal_bindings', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, 'mes_terminal_bindings'):
        return
    for column in ('terminal_code', 'mes_device_name', 'workshop_name', 'process_name', 'equipment_id'):
        _safe_drop_index(f'ix_mes_terminal_bindings_{column}', 'mes_terminal_bindings')
    op.drop_table('mes_terminal_bindings')
