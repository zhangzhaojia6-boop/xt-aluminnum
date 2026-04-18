"""round12 isolation, photo upload and reminders

Revision ID: 0010_round12
Revises: 0009_round11
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0010_round12'
down_revision = '0009_round11'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _has_fk(inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {item.get('name') for item in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'users'):
        if not _has_column(inspector, 'users', 'data_scope_type'):
            op.add_column('users', sa.Column('data_scope_type', sa.String(length=32), nullable=False, server_default='self_team'))
        if not _has_column(inspector, 'users', 'assigned_shift_ids'):
            op.add_column('users', sa.Column('assigned_shift_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        if not _has_column(inspector, 'users', 'is_mobile_user'):
            op.add_column('users', sa.Column('is_mobile_user', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        if not _has_column(inspector, 'users', 'is_reviewer'):
            op.add_column('users', sa.Column('is_reviewer', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        if not _has_column(inspector, 'users', 'is_manager'):
            op.add_column('users', sa.Column('is_manager', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    if _has_table(inspector, 'mobile_shift_reports'):
        for column_name, column in {
            'owner_user_id': sa.Column('owner_user_id', sa.Integer(), nullable=True),
            'submitted_by_user_id': sa.Column('submitted_by_user_id', sa.Integer(), nullable=True),
            'last_action_by_user_id': sa.Column('last_action_by_user_id', sa.Integer(), nullable=True),
            'photo_file_path': sa.Column('photo_file_path', sa.String(length=512), nullable=True),
            'photo_file_name': sa.Column('photo_file_name', sa.String(length=255), nullable=True),
            'photo_uploaded_at': sa.Column('photo_uploaded_at', sa.DateTime(timezone=True), nullable=True),
        }.items():
            if not _has_column(inspector, 'mobile_shift_reports', column_name):
                op.add_column('mobile_shift_reports', column)

        for index_name, columns in {
            'ix_mobile_shift_reports_owner_user_id': ['owner_user_id'],
            'ix_mobile_shift_reports_submitted_by_user_id': ['submitted_by_user_id'],
            'ix_mobile_shift_reports_last_action_by_user_id': ['last_action_by_user_id'],
        }.items():
            if not _has_index(inspector, 'mobile_shift_reports', index_name):
                op.create_index(index_name, 'mobile_shift_reports', columns, unique=False)

        for fk_name, local_column in {
            'fk_mobile_shift_reports_owner_user_id': 'owner_user_id',
            'fk_mobile_shift_reports_submitted_by_user_id': 'submitted_by_user_id',
            'fk_mobile_shift_reports_last_action_by_user_id': 'last_action_by_user_id',
        }.items():
            if not _has_fk(inspector, 'mobile_shift_reports', fk_name):
                op.create_foreign_key(
                    fk_name,
                    'mobile_shift_reports',
                    'users',
                    [local_column],
                    ['id'],
                )

    if not _has_table(inspector, 'mobile_reminder_records'):
        op.create_table(
            'mobile_reminder_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('shift_config_id', sa.Integer(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), nullable=False),
            sa.Column('team_id', sa.Integer(), nullable=True),
            sa.Column('leader_user_id', sa.Integer(), nullable=True),
            sa.Column('reminder_type', sa.String(length=32), nullable=False),
            sa.Column('reminder_status', sa.String(length=16), nullable=False, server_default='pending'),
            sa.Column('reminder_channel', sa.String(length=32), nullable=False, server_default='system'),
            sa.Column('reminder_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_reminded_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('acknowledged_by', sa.Integer(), nullable=True),
            sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('closed_by', sa.Integer(), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['shift_config_id'], ['shift_configs.id']),
            sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
            sa.ForeignKeyConstraint(['leader_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id']),
            sa.ForeignKeyConstraint(['closed_by'], ['users.id']),
            sa.UniqueConstraint(
                'business_date',
                'shift_config_id',
                'workshop_id',
                'team_id',
                'leader_user_id',
                'reminder_type',
                name='uq_mobile_reminder_records_key',
            ),
        )
        for index_name, columns in {
            'ix_mobile_reminder_records_business_date': ['business_date'],
            'ix_mobile_reminder_records_shift_config_id': ['shift_config_id'],
            'ix_mobile_reminder_records_workshop_id': ['workshop_id'],
            'ix_mobile_reminder_records_team_id': ['team_id'],
            'ix_mobile_reminder_records_leader_user_id': ['leader_user_id'],
            'ix_mobile_reminder_records_reminder_type': ['reminder_type'],
            'ix_mobile_reminder_records_reminder_status': ['reminder_status'],
            'ix_mobile_reminder_records_status_date': ['reminder_status', 'business_date'],
        }.items():
            op.create_index(index_name, 'mobile_reminder_records', columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'mobile_reminder_records'):
        for index_name in [
            'ix_mobile_reminder_records_status_date',
            'ix_mobile_reminder_records_reminder_status',
            'ix_mobile_reminder_records_reminder_type',
            'ix_mobile_reminder_records_leader_user_id',
            'ix_mobile_reminder_records_team_id',
            'ix_mobile_reminder_records_workshop_id',
            'ix_mobile_reminder_records_shift_config_id',
            'ix_mobile_reminder_records_business_date',
        ]:
            if _has_index(inspector, 'mobile_reminder_records', index_name):
                op.drop_index(index_name, table_name='mobile_reminder_records')
        op.drop_table('mobile_reminder_records')

    if _has_table(inspector, 'mobile_shift_reports'):
        for fk_name in [
            'fk_mobile_shift_reports_last_action_by_user_id',
            'fk_mobile_shift_reports_submitted_by_user_id',
            'fk_mobile_shift_reports_owner_user_id',
        ]:
            if _has_fk(inspector, 'mobile_shift_reports', fk_name):
                op.drop_constraint(fk_name, 'mobile_shift_reports', type_='foreignkey')
        for index_name in [
            'ix_mobile_shift_reports_last_action_by_user_id',
            'ix_mobile_shift_reports_submitted_by_user_id',
            'ix_mobile_shift_reports_owner_user_id',
        ]:
            if _has_index(inspector, 'mobile_shift_reports', index_name):
                op.drop_index(index_name, table_name='mobile_shift_reports')
        for column_name in [
            'photo_uploaded_at',
            'photo_file_name',
            'photo_file_path',
            'last_action_by_user_id',
            'submitted_by_user_id',
            'owner_user_id',
        ]:
            if _has_column(inspector, 'mobile_shift_reports', column_name):
                op.drop_column('mobile_shift_reports', column_name)

    if _has_table(inspector, 'users'):
        for column_name in ['is_manager', 'is_reviewer', 'is_mobile_user', 'assigned_shift_ids', 'data_scope_type']:
            if _has_column(inspector, 'users', column_name):
                op.drop_column('users', column_name)
