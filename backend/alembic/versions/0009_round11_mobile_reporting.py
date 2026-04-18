"""round11 mobile reporting and user bindings

Revision ID: 0009_round11
Revises: 0008_round7
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = '0009_round11'
down_revision = '0008_round7'
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
        if not _has_column(inspector, 'users', 'team_id'):
            op.add_column('users', sa.Column('team_id', sa.Integer(), nullable=True))
            op.create_index('ix_users_team_id', 'users', ['team_id'], unique=False)
            if _has_table(inspector, 'teams') and not _has_fk(inspector, 'users', 'fk_users_team_id'):
                op.create_foreign_key('fk_users_team_id', 'users', 'teams', ['team_id'], ['id'])
        if not _has_column(inspector, 'users', 'dingtalk_user_id'):
            op.add_column('users', sa.Column('dingtalk_user_id', sa.String(length=64), nullable=True))
            op.create_index('ix_users_dingtalk_user_id', 'users', ['dingtalk_user_id'], unique=False)
        if not _has_column(inspector, 'users', 'dingtalk_union_id'):
            op.add_column('users', sa.Column('dingtalk_union_id', sa.String(length=64), nullable=True))
            op.create_index('ix_users_dingtalk_union_id', 'users', ['dingtalk_union_id'], unique=False)

    if _has_table(inspector, 'attendance_schedules') and not _has_index(
        inspector, 'attendance_schedules', 'ix_attendance_schedules_shift_lookup'
    ):
        op.create_index(
            'ix_attendance_schedules_shift_lookup',
            'attendance_schedules',
            ['business_date', 'workshop_id', 'team_id', 'shift_config_id'],
            unique=False,
        )

    if not _has_table(inspector, 'mobile_shift_reports'):
        op.create_table(
            'mobile_shift_reports',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('shift_config_id', sa.Integer(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), nullable=False),
            sa.Column('team_id', sa.Integer(), nullable=True),
            sa.Column('leader_user_id', sa.Integer(), nullable=True),
            sa.Column('leader_name', sa.String(length=64), nullable=True),
            sa.Column('dingtalk_user_id', sa.String(length=64), nullable=True),
            sa.Column('dingtalk_union_id', sa.String(length=64), nullable=True),
            sa.Column('attendance_count', sa.Integer(), nullable=True),
            sa.Column('input_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('output_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('scrap_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('storage_prepared', sa.Numeric(14, 3), nullable=True),
            sa.Column('storage_finished', sa.Numeric(14, 3), nullable=True),
            sa.Column('shipment_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('contract_received', sa.Numeric(14, 3), nullable=True),
            sa.Column('electricity_daily', sa.Numeric(14, 3), nullable=True),
            sa.Column('gas_daily', sa.Numeric(14, 3), nullable=True),
            sa.Column('has_exception', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('exception_type', sa.String(length=64), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('optional_photo_url', sa.String(length=512), nullable=True),
            sa.Column('report_status', sa.String(length=16), nullable=False, server_default='draft'),
            sa.Column('linked_production_data_id', sa.Integer(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_saved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('returned_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['shift_config_id'], ['shift_configs.id']),
            sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
            sa.ForeignKeyConstraint(['leader_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['linked_production_data_id'], ['shift_production_data.id']),
            sa.UniqueConstraint(
                'business_date',
                'shift_config_id',
                'workshop_id',
                'team_id',
                name='uq_mobile_shift_reports_key',
            ),
        )
        for index_name, columns in {
            'ix_mobile_shift_reports_business_date': ['business_date'],
            'ix_mobile_shift_reports_shift_config_id': ['shift_config_id'],
            'ix_mobile_shift_reports_workshop_id': ['workshop_id'],
            'ix_mobile_shift_reports_team_id': ['team_id'],
            'ix_mobile_shift_reports_leader_user_id': ['leader_user_id'],
            'ix_mobile_shift_reports_dingtalk_user_id': ['dingtalk_user_id'],
            'ix_mobile_shift_reports_dingtalk_union_id': ['dingtalk_union_id'],
            'ix_mobile_shift_reports_report_status': ['report_status'],
            'ix_mobile_shift_reports_linked_production_data_id': ['linked_production_data_id'],
            'ix_mobile_shift_reports_status_date': ['report_status', 'business_date'],
        }.items():
            op.create_index(index_name, 'mobile_shift_reports', columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'mobile_shift_reports'):
        for index_name in [
            'ix_mobile_shift_reports_status_date',
            'ix_mobile_shift_reports_linked_production_data_id',
            'ix_mobile_shift_reports_report_status',
            'ix_mobile_shift_reports_dingtalk_union_id',
            'ix_mobile_shift_reports_dingtalk_user_id',
            'ix_mobile_shift_reports_leader_user_id',
            'ix_mobile_shift_reports_team_id',
            'ix_mobile_shift_reports_workshop_id',
            'ix_mobile_shift_reports_shift_config_id',
            'ix_mobile_shift_reports_business_date',
        ]:
            if _has_index(inspector, 'mobile_shift_reports', index_name):
                op.drop_index(index_name, table_name='mobile_shift_reports')
        op.drop_table('mobile_shift_reports')

    if _has_table(inspector, 'attendance_schedules') and _has_index(
        inspector, 'attendance_schedules', 'ix_attendance_schedules_shift_lookup'
    ):
        op.drop_index('ix_attendance_schedules_shift_lookup', table_name='attendance_schedules')

    if _has_table(inspector, 'users'):
        if _has_index(inspector, 'users', 'ix_users_dingtalk_union_id'):
            op.drop_index('ix_users_dingtalk_union_id', table_name='users')
        if _has_column(inspector, 'users', 'dingtalk_union_id'):
            op.drop_column('users', 'dingtalk_union_id')

        if _has_index(inspector, 'users', 'ix_users_dingtalk_user_id'):
            op.drop_index('ix_users_dingtalk_user_id', table_name='users')
        if _has_column(inspector, 'users', 'dingtalk_user_id'):
            op.drop_column('users', 'dingtalk_user_id')

        if _has_fk(inspector, 'users', 'fk_users_team_id'):
            op.drop_constraint('fk_users_team_id', 'users', type_='foreignkey')
        if _has_index(inspector, 'users', 'ix_users_team_id'):
            op.drop_index('ix_users_team_id', table_name='users')
        if _has_column(inspector, 'users', 'team_id'):
            op.drop_column('users', 'team_id')
