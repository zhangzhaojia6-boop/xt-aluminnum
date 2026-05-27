"""fix machine operator roles: shift_leader → machine_operator for equipment-bound users

Revision ID: 0033_fix_machine_operator_roles
Revises: 0032_truth_source_three_layer
Create Date: 2026-05-27 18:00:00.000000
"""

from alembic import op


revision = '0033_fix_machine_operator_roles'
down_revision = '0032_truth_source_three_layer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE users
        SET role = 'machine_operator'
        WHERE id IN (
            SELECT e.bound_user_id
            FROM equipment e
            WHERE e.bound_user_id IS NOT NULL
              AND e.equipment_type NOT IN ('virtual_role_qr', 'virtual_workshop_qr')
        )
        AND role = 'shift_leader'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE users
        SET role = 'shift_leader'
        WHERE id IN (
            SELECT e.bound_user_id
            FROM equipment e
            WHERE e.bound_user_id IS NOT NULL
              AND e.equipment_type NOT IN ('virtual_role_qr', 'virtual_workshop_qr')
        )
        AND role = 'machine_operator'
    """)
