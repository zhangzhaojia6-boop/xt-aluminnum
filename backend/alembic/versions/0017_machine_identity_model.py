"""machine identity model

Revision ID: 0017_machine_identity_model
Revises: 0016_realtime_events_persistent
Create Date: 2026-03-28 22:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0017_machine_identity_model'
down_revision = '0016_realtime_events_persistent'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('pin_code', sa.String(length=6), nullable=True),
    )

    op.add_column(
        'equipment',
        sa.Column('operational_status', sa.String(length=20), nullable=False, server_default='stopped'),
    )
    op.add_column(
        'equipment',
        sa.Column('shift_mode', sa.String(length=10), nullable=False, server_default='three'),
    )
    op.add_column(
        'equipment',
        sa.Column('assigned_shift_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'equipment',
        sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'equipment',
        sa.Column('qr_code', sa.String(length=100), nullable=True),
    )
    op.add_column(
        'equipment',
        sa.Column('bound_user_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'equipment',
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    op.create_index('ix_equipment_qr_code', 'equipment', ['qr_code'], unique=True)
    op.create_index('ix_equipment_bound_user_id', 'equipment', ['bound_user_id'], unique=False)
    op.create_foreign_key(
        'fk_equipment_bound_user_id_users',
        'equipment',
        'users',
        ['bound_user_id'],
        ['id'],
    )

    op.execute("UPDATE equipment SET operational_status = 'stopped' WHERE operational_status IS NULL")
    op.execute("UPDATE equipment SET shift_mode = 'three' WHERE shift_mode IS NULL")
    op.execute("UPDATE equipment SET sort_order = 0 WHERE sort_order IS NULL")

    op.alter_column('equipment', 'operational_status', server_default=None)
    op.alter_column('equipment', 'shift_mode', server_default=None)
    op.alter_column('equipment', 'sort_order', server_default=None)


def downgrade() -> None:
    op.drop_constraint('fk_equipment_bound_user_id_users', 'equipment', type_='foreignkey')
    op.drop_index('ix_equipment_bound_user_id', table_name='equipment')
    op.drop_index('ix_equipment_qr_code', table_name='equipment')
    op.drop_column('equipment', 'sort_order')
    op.drop_column('equipment', 'bound_user_id')
    op.drop_column('equipment', 'qr_code')
    op.drop_column('equipment', 'custom_fields')
    op.drop_column('equipment', 'assigned_shift_ids')
    op.drop_column('equipment', 'shift_mode')
    op.drop_column('equipment', 'operational_status')
    op.drop_column('users', 'pin_code')
