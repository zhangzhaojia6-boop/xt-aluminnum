"""daily fact scheduled snapshot key

Revision ID: 0053_daily_fact_snapshot_key
Revises: 0052_hermes_factory_brain
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0053_daily_fact_snapshot_key'
down_revision = '0052_hermes_factory_brain'
branch_labels = None
depends_on = None


TABLE_NAME = 'daily_fact_bundle_snapshots'
INDEX_NAME = 'ix_daily_fact_bundle_snapshots_snapshot_key'
SCHEDULED_REASON = 'scheduled_daily_closure'
LEGACY_REASON = 'scheduled_daily_closure_legacy_0053'


def _backfill_scheduled_snapshot_keys(bind: sa.Connection) -> None:
    snapshots = sa.table(
        TABLE_NAME,
        sa.column('id', sa.Integer()),
        sa.column('run_id', sa.Integer()),
        sa.column('snapshot_reason', sa.String()),
        sa.column('snapshot_key', sa.String()),
        sa.column('created_at', sa.DateTime()),
    )
    runs = sa.table(
        'daily_fact_bundle_runs',
        sa.column('id', sa.Integer()),
        sa.column('run_key', sa.String()),
    )
    rows = bind.execute(
        sa.select(
            snapshots.c.id,
            snapshots.c.run_id,
            snapshots.c.created_at,
            runs.c.run_key,
        )
        .select_from(snapshots.outerjoin(runs, snapshots.c.run_id == runs.c.id))
        .where(snapshots.c.snapshot_reason == SCHEDULED_REASON)
        .order_by(
            snapshots.c.run_id.asc(),
            snapshots.c.created_at.desc(),
            snapshots.c.id.desc(),
        )
    ).mappings().all()

    canonical_by_run: dict[int, dict] = {}
    legacy_ids: list[int] = []
    for row in rows:
        run_id = row['run_id']
        run_key = row['run_key']
        if run_id is None or not run_key:
            legacy_ids.append(row['id'])
        elif run_id in canonical_by_run:
            legacy_ids.append(row['id'])
        else:
            canonical_by_run[run_id] = row

    if legacy_ids:
        bind.execute(
            sa.update(snapshots)
            .where(snapshots.c.id.in_(legacy_ids))
            .values(snapshot_reason=LEGACY_REASON, snapshot_key=None)
        )
    for row in canonical_by_run.values():
        bind.execute(
            sa.update(snapshots)
            .where(snapshots.c.id == row['id'])
            .values(snapshot_key=f"{SCHEDULED_REASON}:{row['run_key']}")
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns(TABLE_NAME)}
    if 'snapshot_key' not in columns:
        op.add_column(TABLE_NAME, sa.Column('snapshot_key', sa.String(length=200), nullable=True))

    _backfill_scheduled_snapshot_keys(bind)

    inspector = sa.inspect(bind)
    indexes = {index['name'] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, ['snapshot_key'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    snapshots = sa.table(
        TABLE_NAME,
        sa.column('snapshot_reason', sa.String()),
    )
    bind.execute(
        sa.update(snapshots)
        .where(snapshots.c.snapshot_reason == LEGACY_REASON)
        .values(snapshot_reason=SCHEDULED_REASON)
    )
    inspector = sa.inspect(bind)
    indexes = {index['name'] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)

    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns(TABLE_NAME)}
    if 'snapshot_key' in columns:
        with op.batch_alter_table(TABLE_NAME) as batch_op:
            batch_op.drop_column('snapshot_key')
