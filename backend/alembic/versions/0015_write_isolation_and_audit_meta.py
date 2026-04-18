"""write isolation and audit metadata

Revision ID: 0015_write_isolation_and_audit_meta
Revises: 0014_photo_to_form_ocr
Create Date: 2026-03-28 12:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_write_isolation_and_audit_meta'
down_revision = '0014_photo_to_form_ocr'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('user_agent', sa.String(length=512), nullable=True))

    op.add_column('work_order_entries', sa.Column('created_by_user_id', sa.Integer(), nullable=True))
    op.execute('UPDATE work_order_entries SET created_by_user_id = created_by WHERE created_by_user_id IS NULL')
    op.create_foreign_key(
        'fk_work_order_entries_created_by_user_id_users',
        'work_order_entries',
        'users',
        ['created_by_user_id'],
        ['id'],
    )
    op.create_index(
        'ix_work_order_entries_created_by_user_id',
        'work_order_entries',
        ['created_by_user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_work_order_entries_created_by_user_id', table_name='work_order_entries')
    op.drop_constraint('fk_work_order_entries_created_by_user_id_users', 'work_order_entries', type_='foreignkey')
    op.drop_column('work_order_entries', 'created_by_user_id')
    op.drop_column('audit_logs', 'user_agent')
