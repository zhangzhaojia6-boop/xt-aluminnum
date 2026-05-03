"""create rule configs

Revision ID: 0025_rule_configs
Revises: 0024_ai_briefing_owner_scope
Create Date: 2026-05-03 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0025_rule_configs'
down_revision = '0024_ai_briefing_owner_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rule_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scope_type', sa.String(length=16), nullable=False),
        sa.Column('scope_key', sa.String(length=64), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.String(length=64), nullable=False),
        sa.Column('value_type', sa.String(length=16), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_key', 'key', name='uq_rule_configs_scope_key'),
    )
    op.create_index('ix_rule_configs_id', 'rule_configs', ['id'], unique=False)
    op.create_index('ix_rule_configs_scope_type', 'rule_configs', ['scope_type'], unique=False)
    op.create_index('ix_rule_configs_scope_key', 'rule_configs', ['scope_key'], unique=False)
    op.create_index('ix_rule_configs_key', 'rule_configs', ['key'], unique=False)
    op.create_index('ix_rule_configs_updated_by', 'rule_configs', ['updated_by'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rule_configs_updated_by', table_name='rule_configs')
    op.drop_index('ix_rule_configs_key', table_name='rule_configs')
    op.drop_index('ix_rule_configs_scope_key', table_name='rule_configs')
    op.drop_index('ix_rule_configs_scope_type', table_name='rule_configs')
    op.drop_index('ix_rule_configs_id', table_name='rule_configs')
    op.drop_table('rule_configs')
