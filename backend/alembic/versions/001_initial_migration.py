"""legacy placeholder migration

Revision ID: 001
Revises: 0001_initial
Create Date: 2026-03-25
"""

from alembic import op

revision = '001'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally empty. Keeps compatibility with environments
    # that may have referenced revision "001".
    pass


def downgrade() -> None:
    pass
