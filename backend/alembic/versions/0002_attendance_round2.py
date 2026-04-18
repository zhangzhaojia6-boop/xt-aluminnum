"""round2 attendance enhancement

Revision ID: 0002_attendance_round2
Revises: 001
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


revision = '0002_attendance_round2'
down_revision = '001'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _has_unique(inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {item['name'] for item in inspector.get_unique_constraints(table_name)}


def _has_fk(inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {item.get('name') for item in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # attendance_schedules
    if _has_table(inspector, 'attendance_schedules'):
        if _has_column(inspector, 'attendance_schedules', 'shift_id') and not _has_column(inspector, 'attendance_schedules', 'shift_config_id'):
            op.alter_column('attendance_schedules', 'shift_id', new_column_name='shift_config_id')

        if not _has_column(inspector, 'attendance_schedules', 'workshop_id'):
            op.add_column('attendance_schedules', sa.Column('workshop_id', sa.Integer(), nullable=True))
        if not _has_column(inspector, 'attendance_schedules', 'import_batch_id'):
            op.add_column('attendance_schedules', sa.Column('import_batch_id', sa.Integer(), nullable=True))

        if not _has_fk(inspector, 'attendance_schedules', 'fk_attendance_schedules_workshop_id'):
            op.create_foreign_key(
                'fk_attendance_schedules_workshop_id',
                'attendance_schedules',
                'workshops',
                ['workshop_id'],
                ['id'],
            )
        if not _has_fk(inspector, 'attendance_schedules', 'fk_attendance_schedules_import_batch_id'):
            op.create_foreign_key(
                'fk_attendance_schedules_import_batch_id',
                'attendance_schedules',
                'import_batches',
                ['import_batch_id'],
                ['id'],
            )

    # clock_records
    if _has_table(inspector, 'clock_records'):
        if _has_column(inspector, 'clock_records', 'clock_time') and not _has_column(inspector, 'clock_records', 'clock_datetime'):
            op.alter_column('clock_records', 'clock_time', new_column_name='clock_datetime')

        if not _has_column(inspector, 'clock_records', 'employee_no'):
            op.add_column('clock_records', sa.Column('employee_no', sa.String(length=32), nullable=True))
        if not _has_column(inspector, 'clock_records', 'dingtalk_user_id'):
            op.add_column('clock_records', sa.Column('dingtalk_user_id', sa.String(length=64), nullable=True))
        if not _has_column(inspector, 'clock_records', 'dingtalk_record_id'):
            op.add_column('clock_records', sa.Column('dingtalk_record_id', sa.String(length=128), nullable=True))
        if not _has_column(inspector, 'clock_records', 'location_name'):
            op.add_column('clock_records', sa.Column('location_name', sa.String(length=128), nullable=True))
        if not _has_column(inspector, 'clock_records', 'import_batch_id'):
            op.add_column('clock_records', sa.Column('import_batch_id', sa.Integer(), nullable=True))

        op.execute(
            sa.text(
                """
                UPDATE clock_records c
                SET employee_no = e.employee_no
                FROM employees e
                WHERE c.employee_id = e.id AND c.employee_no IS NULL
                """
            )
        )

        op.execute(sa.text("UPDATE clock_records SET device_id = '' WHERE device_id IS NULL"))

        op.alter_column('clock_records', 'employee_id', existing_type=sa.Integer(), nullable=True)
        op.alter_column('clock_records', 'device_id', existing_type=sa.String(length=64), nullable=False, server_default='')
        op.alter_column('clock_records', 'employee_no', existing_type=sa.String(length=32), nullable=False)
        op.alter_column('clock_records', 'source', existing_type=sa.String(length=16), type_=sa.String(length=32))

        if not _has_fk(inspector, 'clock_records', 'fk_clock_records_import_batch_id'):
            op.create_foreign_key('fk_clock_records_import_batch_id', 'clock_records', 'import_batches', ['import_batch_id'], ['id'])

        if not _has_index(inspector, 'clock_records', 'ix_clock_records_employee_no'):
            op.create_index('ix_clock_records_employee_no', 'clock_records', ['employee_no'], unique=False)
        if not _has_index(inspector, 'clock_records', 'ix_clock_records_dingtalk_user_id'):
            op.create_index('ix_clock_records_dingtalk_user_id', 'clock_records', ['dingtalk_user_id'], unique=False)
        if not _has_unique(inspector, 'clock_records', 'uq_clock_dingtalk_record_id'):
            op.create_unique_constraint('uq_clock_dingtalk_record_id', 'clock_records', ['dingtalk_record_id'])
        if not _has_unique(inspector, 'clock_records', 'uq_clock_unique_key'):
            op.create_unique_constraint(
                'uq_clock_unique_key',
                'clock_records',
                ['employee_id', 'clock_datetime', 'clock_type', 'device_id'],
            )

    # attendance_results
    if _has_table(inspector, 'attendance_results'):
        if _has_column(inspector, 'attendance_results', 'shift_id') and not _has_column(inspector, 'attendance_results', 'shift_config_id'):
            op.alter_column('attendance_results', 'shift_id', new_column_name='shift_config_id')

        for name, coltype in [
            ('employee_no', sa.String(length=32)),
            ('employee_name', sa.String(length=64)),
            ('team_id', sa.Integer()),
            ('workshop_id', sa.Integer()),
            ('auto_shift_config_id', sa.Integer()),
            ('data_status', sa.String(length=16)),
            ('is_manual_override', sa.Boolean()),
            ('override_reason', sa.Text()),
            ('override_by', sa.Integer()),
            ('override_at', sa.DateTime(timezone=True)),
        ]:
            if not _has_column(inspector, 'attendance_results', name):
                op.add_column('attendance_results', sa.Column(name, coltype, nullable=True))

        op.execute(
            sa.text(
                """
                UPDATE attendance_results r
                SET employee_no = e.employee_no,
                    employee_name = e.name,
                    team_id = e.team_id,
                    workshop_id = e.workshop_id
                FROM employees e
                WHERE r.employee_id = e.id
                """
            )
        )

        op.alter_column('attendance_results', 'employee_no', existing_type=sa.String(length=32), nullable=False)
        op.alter_column('attendance_results', 'employee_name', existing_type=sa.String(length=64), nullable=False)
        op.alter_column('attendance_results', 'data_status', existing_type=sa.String(length=16), nullable=False, server_default='auto')
        op.alter_column(
            'attendance_results',
            'is_manual_override',
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
        op.alter_column('attendance_results', 'attendance_status', existing_type=sa.String(length=16), type_=sa.String(length=32))

        if _has_column(inspector, 'attendance_results', 'exception_flag'):
            op.drop_column('attendance_results', 'exception_flag')

        if not _has_fk(inspector, 'attendance_results', 'fk_attendance_results_team_id'):
            op.create_foreign_key('fk_attendance_results_team_id', 'attendance_results', 'teams', ['team_id'], ['id'])
        if not _has_fk(inspector, 'attendance_results', 'fk_attendance_results_workshop_id'):
            op.create_foreign_key('fk_attendance_results_workshop_id', 'attendance_results', 'workshops', ['workshop_id'], ['id'])
        if not _has_fk(inspector, 'attendance_results', 'fk_attendance_results_auto_shift_config_id'):
            op.create_foreign_key(
                'fk_attendance_results_auto_shift_config_id',
                'attendance_results',
                'shift_configs',
                ['auto_shift_config_id'],
                ['id'],
            )
        if not _has_fk(inspector, 'attendance_results', 'fk_attendance_results_override_by'):
            op.create_foreign_key('fk_attendance_results_override_by', 'attendance_results', 'users', ['override_by'], ['id'])

        if not _has_index(inspector, 'attendance_results', 'ix_attendance_results_data_status'):
            op.create_index('ix_attendance_results_data_status', 'attendance_results', ['data_status'], unique=False)
        if not _has_index(inspector, 'attendance_results', 'ix_attendance_results_employee_no'):
            op.create_index('ix_attendance_results_employee_no', 'attendance_results', ['employee_no'], unique=False)

    # attendance_exceptions
    if _has_table(inspector, 'attendance_exceptions'):
        if _has_column(inspector, 'attendance_exceptions', 'description') and not _has_column(inspector, 'attendance_exceptions', 'exception_desc'):
            op.alter_column('attendance_exceptions', 'description', new_column_name='exception_desc')

        for name, coltype in [
            ('attendance_result_id', sa.Integer()),
            ('shift_config_id', sa.Integer()),
            ('severity', sa.String(length=16)),
            ('resolve_action', sa.String(length=32)),
            ('resolve_note', sa.Text()),
        ]:
            if not _has_column(inspector, 'attendance_exceptions', name):
                op.add_column('attendance_exceptions', sa.Column(name, coltype, nullable=True))

        op.alter_column('attendance_exceptions', 'exception_desc', existing_type=sa.String(length=256), type_=sa.Text(), nullable=False)
        op.alter_column('attendance_exceptions', 'status', existing_type=sa.String(length=16), nullable=False, server_default='open')
        op.alter_column('attendance_exceptions', 'severity', existing_type=sa.String(length=16), nullable=False, server_default='warning')

        if not _has_fk(inspector, 'attendance_exceptions', 'fk_attendance_exceptions_attendance_result_id'):
            op.create_foreign_key(
                'fk_attendance_exceptions_attendance_result_id',
                'attendance_exceptions',
                'attendance_results',
                ['attendance_result_id'],
                ['id'],
            )
        if not _has_fk(inspector, 'attendance_exceptions', 'fk_attendance_exceptions_shift_config_id'):
            op.create_foreign_key(
                'fk_attendance_exceptions_shift_config_id',
                'attendance_exceptions',
                'shift_configs',
                ['shift_config_id'],
                ['id'],
            )

        if not _has_index(inspector, 'attendance_exceptions', 'ix_attendance_exceptions_status'):
            op.create_index('ix_attendance_exceptions_status', 'attendance_exceptions', ['status'], unique=False)

    if not _has_table(inspector, 'attendance_process_logs'):
        op.create_table(
            'attendance_process_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('process_date', sa.Date(), nullable=False),
            sa.Column('trigger_type', sa.String(length=32), nullable=False, server_default='manual'),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='completed'),
            sa.Column('message', sa.String(length=255), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        )
        op.create_index('ix_attendance_process_logs_process_date', 'attendance_process_logs', ['process_date'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'attendance_process_logs'):
        if _has_index(inspector, 'attendance_process_logs', 'ix_attendance_process_logs_process_date'):
            op.drop_index('ix_attendance_process_logs_process_date', table_name='attendance_process_logs')
        op.drop_table('attendance_process_logs')

    if _has_table(inspector, 'attendance_exceptions'):
        if _has_index(inspector, 'attendance_exceptions', 'ix_attendance_exceptions_status'):
            op.drop_index('ix_attendance_exceptions_status', table_name='attendance_exceptions')

    if _has_table(inspector, 'attendance_results'):
        if _has_index(inspector, 'attendance_results', 'ix_attendance_results_employee_no'):
            op.drop_index('ix_attendance_results_employee_no', table_name='attendance_results')
        if _has_index(inspector, 'attendance_results', 'ix_attendance_results_data_status'):
            op.drop_index('ix_attendance_results_data_status', table_name='attendance_results')

    if _has_table(inspector, 'clock_records'):
        if _has_index(inspector, 'clock_records', 'ix_clock_records_dingtalk_user_id'):
            op.drop_index('ix_clock_records_dingtalk_user_id', table_name='clock_records')
        if _has_index(inspector, 'clock_records', 'ix_clock_records_employee_no'):
            op.drop_index('ix_clock_records_employee_no', table_name='clock_records')
