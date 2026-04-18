"""add workshop template configs

Revision ID: 0019_workshop_template_configs
Revises: 0018_workshop_type_templates
Create Date: 2026-03-30 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019_workshop_template_configs'
down_revision = '0018_workshop_type_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workshop_template_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_key', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=64), nullable=False),
        sa.Column('tempo', sa.String(length=16), nullable=False),
        sa.Column('supports_ocr', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('entry_fields', sa.JSON(), nullable=False),
        sa.Column('extra_fields', sa.JSON(), nullable=False),
        sa.Column('qc_fields', sa.JSON(), nullable=False),
        sa.Column('readonly_fields', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_key'),
    )
    op.create_index('ix_workshop_template_configs_id', 'workshop_template_configs', ['id'], unique=False)
    op.create_index('ix_workshop_template_configs_template_key', 'workshop_template_configs', ['template_key'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_workshop_template_configs_template_key', table_name='workshop_template_configs')
    op.drop_index('ix_workshop_template_configs_id', table_name='workshop_template_configs')
    op.drop_table('workshop_template_configs')
