"""attendance secondary confirmation tables

Revision ID: 0013_attendance_secondary_confirmation
Revises: 0012_work_order_template_payloads
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa


revision = '0013_attendance_secondary_confirmation'
down_revision = '0012_work_order_template_payloads'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'attendance_clock_records'):
        op.create_table(
            'attendance_clock_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('employee_id', sa.Integer(), nullable=True),
            sa.Column('clock_time', sa.DateTime(timezone=True), nullable=False),
            sa.Column('clock_type', sa.String(length=16), nullable=False),
            sa.Column('dingtalk_id', sa.String(length=128), nullable=False),
            sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
            sa.UniqueConstraint('dingtalk_id', name='uq_attendance_clock_records_dingtalk_id'),
        )
        for index_name, columns in {
            'ix_attendance_clock_records_id': ['id'],
            'ix_attendance_clock_records_employee_id': ['employee_id'],
            'ix_attendance_clock_records_clock_time': ['clock_time'],
            'ix_attendance_clock_records_clock_type': ['clock_type'],
            'ix_attendance_clock_records_dingtalk_id': ['dingtalk_id'],
        }.items():
            op.create_index(index_name, 'attendance_clock_records', columns, unique=False)

    if not _has_table(inspector, 'shift_attendance_confirmations'):
        op.create_table(
            'shift_attendance_confirmations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('workshop_id', sa.Integer(), nullable=False),
            sa.Column('machine_id', sa.Integer(), nullable=False),
            sa.Column('shift_id', sa.Integer(), nullable=False),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('confirmed_by', sa.Integer(), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='draft'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
            sa.ForeignKeyConstraint(['machine_id'], ['equipment.id']),
            sa.ForeignKeyConstraint(['shift_id'], ['shift_configs.id']),
            sa.ForeignKeyConstraint(['confirmed_by'], ['users.id']),
            sa.UniqueConstraint(
                'workshop_id',
                'machine_id',
                'shift_id',
                'business_date',
                name='uq_shift_attendance_confirmation',
            ),
        )
        for index_name, columns in {
            'ix_shift_attendance_confirmations_id': ['id'],
            'ix_shift_attendance_confirmations_workshop_id': ['workshop_id'],
            'ix_shift_attendance_confirmations_machine_id': ['machine_id'],
            'ix_shift_attendance_confirmations_shift_id': ['shift_id'],
            'ix_shift_attendance_confirmations_business_date': ['business_date'],
            'ix_shift_attendance_confirmation_status_date': ['status', 'business_date'],
        }.items():
            op.create_index(index_name, 'shift_attendance_confirmations', columns, unique=False)

    if not _has_table(inspector, 'employee_attendance_details'):
        op.create_table(
            'employee_attendance_details',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('confirmation_id', sa.Integer(), nullable=False),
            sa.Column('employee_id', sa.Integer(), nullable=False),
            sa.Column('dingtalk_clock_in', sa.Time(), nullable=True),
            sa.Column('dingtalk_clock_out', sa.Time(), nullable=True),
            sa.Column('leader_status', sa.String(length=32), nullable=False, server_default='present'),
            sa.Column('late_minutes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('early_leave_minutes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('override_reason', sa.Text(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('hr_status', sa.String(length=16), nullable=False, server_default='pending'),
            sa.Column('hr_review_note', sa.Text(), nullable=True),
            sa.Column('hr_reviewed_by', sa.Integer(), nullable=True),
            sa.Column('hr_reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['confirmation_id'], ['shift_attendance_confirmations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
            sa.ForeignKeyConstraint(['hr_reviewed_by'], ['users.id']),
            sa.UniqueConstraint(
                'confirmation_id',
                'employee_id',
                name='uq_employee_attendance_detail_confirmation_employee',
            ),
        )
        for index_name, columns in {
            'ix_employee_attendance_details_id': ['id'],
            'ix_employee_attendance_details_confirmation_id': ['confirmation_id'],
            'ix_employee_attendance_details_employee_id': ['employee_id'],
            'ix_employee_attendance_details_leader_status': ['leader_status'],
            'ix_employee_attendance_details_hr_status': ['hr_status'],
            'ix_employee_attendance_details_hr_reviewed_by': ['hr_reviewed_by'],
        }.items():
            op.create_index(index_name, 'employee_attendance_details', columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'employee_attendance_details'):
        for index_name in [
            'ix_employee_attendance_details_hr_reviewed_by',
            'ix_employee_attendance_details_hr_status',
            'ix_employee_attendance_details_leader_status',
            'ix_employee_attendance_details_employee_id',
            'ix_employee_attendance_details_confirmation_id',
            'ix_employee_attendance_details_id',
        ]:
            if _has_index(inspector, 'employee_attendance_details', index_name):
                op.drop_index(index_name, table_name='employee_attendance_details')
        op.drop_table('employee_attendance_details')

    if _has_table(inspector, 'shift_attendance_confirmations'):
        for index_name in [
            'ix_shift_attendance_confirmation_status_date',
            'ix_shift_attendance_confirmations_business_date',
            'ix_shift_attendance_confirmations_shift_id',
            'ix_shift_attendance_confirmations_machine_id',
            'ix_shift_attendance_confirmations_workshop_id',
            'ix_shift_attendance_confirmations_id',
        ]:
            if _has_index(inspector, 'shift_attendance_confirmations', index_name):
                op.drop_index(index_name, table_name='shift_attendance_confirmations')
        op.drop_table('shift_attendance_confirmations')

    if _has_table(inspector, 'attendance_clock_records'):
        for index_name in [
            'ix_attendance_clock_records_dingtalk_id',
            'ix_attendance_clock_records_clock_type',
            'ix_attendance_clock_records_clock_time',
            'ix_attendance_clock_records_employee_id',
            'ix_attendance_clock_records_id',
        ]:
            if _has_index(inspector, 'attendance_clock_records', index_name):
                op.drop_index(index_name, table_name='attendance_clock_records')
        op.drop_table('attendance_clock_records')
