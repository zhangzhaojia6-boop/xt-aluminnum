"""add workshop type to workshops

Revision ID: 0018_workshop_type_templates
Revises: 0017_machine_identity_model
Create Date: 2026-03-30 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0018_workshop_type_templates'
down_revision = '0017_machine_identity_model'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('workshops', sa.Column('workshop_type', sa.String(length=32), nullable=True))
    op.create_index('ix_workshops_workshop_type', 'workshops', ['workshop_type'], unique=False)

    op.execute(
        """
        UPDATE workshops
        SET workshop_type = CASE code
            WHEN 'ZD' THEN 'casting'
            WHEN 'ZR2' THEN 'casting'
            WHEN 'ZR3' THEN 'casting'
            WHEN 'RZ' THEN 'hot_roll'
            WHEN 'LZ2050' THEN 'cold_roll'
            WHEN 'LZ1450' THEN 'cold_roll'
            WHEN 'LZ3' THEN 'cold_roll'
            WHEN 'JZ' THEN 'finishing'
            WHEN 'JZ2' THEN 'finishing'
            WHEN 'JQ' THEN 'shearing'
            ELSE workshop_type
        END
        """
    )


def downgrade() -> None:
    op.drop_index('ix_workshops_workshop_type', table_name='workshops')
    op.drop_column('workshops', 'workshop_type')
