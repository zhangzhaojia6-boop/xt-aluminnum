"""unify shift configs

Revision ID: 0036_unify_shift_configs
Revises: 0035_mes_daily_wip_snapshots
Create Date: 2026-06-02 17:20:00.000000
"""

from alembic import op


revision = '0036_unify_shift_configs'
down_revision = '0035_mes_daily_wip_snapshots'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO shift_configs
            (code, name, shift_type, start_time, end_time, is_cross_day, business_day_offset,
             late_tolerance_minutes, early_tolerance_minutes, sort_order, is_active, created_at, updated_at)
        VALUES
            ('A', '长白班', 'day', '07:30:00', '15:30:00', false, 0, 30, 30, 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('B', '小夜班', 'evening', '15:30:00', '23:30:00', false, 0, 30, 30, 2, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('C', '大夜班', 'night', '23:30:00', '07:30:00', true, 0, 30, 30, 3, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            shift_type = EXCLUDED.shift_type,
            start_time = EXCLUDED.start_time,
            end_time = EXCLUDED.end_time,
            is_cross_day = EXCLUDED.is_cross_day,
            business_day_offset = EXCLUDED.business_day_offset,
            late_tolerance_minutes = EXCLUDED.late_tolerance_minutes,
            early_tolerance_minutes = EXCLUDED.early_tolerance_minutes,
            sort_order = EXCLUDED.sort_order,
            is_active = true,
            updated_at = CURRENT_TIMESTAMP
        """
    )
    op.execute(
        """
        UPDATE shift_configs
        SET
            is_active = false,
            name = CASE code
                WHEN 'DAY' THEN '长白班'
                WHEN 'MID' THEN '小夜班'
                WHEN 'NIGHT' THEN '大夜班'
                ELSE name
            END
        WHERE code IN ('DAY', 'MID', 'NIGHT')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE shift_configs
        SET name = CASE code
            WHEN 'C' THEN '大夜'
            WHEN 'A' THEN '长白班'
            WHEN 'B' THEN '小夜'
            ELSE name
        END
        WHERE code IN ('C', 'A', 'B')
        """
    )
