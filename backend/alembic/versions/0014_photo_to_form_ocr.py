"""photo to form ocr support

Revision ID: 0014_photo_to_form_ocr
Revises: 0013_attendance_secondary_confirmation
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa


revision = '0014_photo_to_form_ocr'
down_revision = '0013_attendance_secondary_confirmation'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'ocr_submissions'):
        op.create_table(
            'ocr_submissions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('image_path', sa.String(length=512), nullable=False),
            sa.Column('workshop_type', sa.String(length=64), nullable=False),
            sa.Column('extracted_json', sa.JSON(), nullable=True),
            sa.Column('verified_json', sa.JSON(), nullable=True),
            sa.Column('linked_entry_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending_review'),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['linked_entry_id'], ['work_order_entries.id']),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        )
        for index_name, columns in {
            'ix_ocr_submissions_id': ['id'],
            'ix_ocr_submissions_workshop_type': ['workshop_type'],
            'ix_ocr_submissions_linked_entry_id': ['linked_entry_id'],
            'ix_ocr_submissions_status': ['status'],
            'ix_ocr_submissions_created_by': ['created_by'],
        }.items():
            op.create_index(index_name, 'ocr_submissions', columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'ocr_submissions'):
        for index_name in [
            'ix_ocr_submissions_created_by',
            'ix_ocr_submissions_status',
            'ix_ocr_submissions_linked_entry_id',
            'ix_ocr_submissions_workshop_type',
            'ix_ocr_submissions_id',
        ]:
            if _has_index(inspector, 'ocr_submissions', index_name):
                op.drop_index(index_name, table_name='ocr_submissions')
        op.drop_table('ocr_submissions')
