"""make user dingtalk bindings unique

Revision ID: 0026_unique_user_dingtalk_bindings
Revises: 0025_rule_configs
Create Date: 2026-05-03 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0026_unique_user_dingtalk_bindings'
down_revision = '0025_rule_configs'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _normalize_and_clear_duplicates(column_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE users
            SET {column_name} = trim({column_name})
            WHERE {column_name} IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE users
            SET {column_name} = NULL
            WHERE {column_name} IS NOT NULL
              AND trim({column_name}) = ''
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE users
            SET {column_name} = NULL
            WHERE {column_name} IS NOT NULL
              AND trim({column_name}) <> ''
              AND id NOT IN (
                SELECT keep_id
                FROM (
                  SELECT COALESCE(
                    MIN(CASE WHEN is_active IS TRUE THEN id ELSE NULL END),
                    MIN(id)
                  ) AS keep_id
                  FROM users
                  WHERE {column_name} IS NOT NULL
                    AND trim({column_name}) <> ''
                  GROUP BY {column_name}
                ) AS kept_users
              )
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, 'users'):
        return

    for column_name in ('dingtalk_user_id', 'dingtalk_union_id'):
        index_name = f'ix_users_{column_name}'
        _normalize_and_clear_duplicates(column_name)
        if _has_index(inspector, 'users', index_name):
            op.drop_index(index_name, table_name='users')
        op.create_index(index_name, 'users', [column_name], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, 'users'):
        return

    for column_name in ('dingtalk_union_id', 'dingtalk_user_id'):
        index_name = f'ix_users_{column_name}'
        if _has_index(inspector, 'users', index_name):
            op.drop_index(index_name, table_name='users')
        op.create_index(index_name, 'users', [column_name], unique=False)
