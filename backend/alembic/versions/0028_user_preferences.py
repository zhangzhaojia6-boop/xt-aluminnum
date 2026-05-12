"""user_preferences table for per-user theme opt-in

Revision ID: 0028_user_preferences
Revises: 0027_executive_dashboard
Create Date: 2026-05-10 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0028_user_preferences'
down_revision = '0027_executive_dashboard'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'user_preferences'):
        return

    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('theme', sa.String(length=16), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='uq_user_preferences_user_id'),
    )
    op.create_index(
        'ix_user_preferences_user_id',
        'user_preferences',
        ['user_id'],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'user_preferences'):
        return

    op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
    op.drop_table('user_preferences')
