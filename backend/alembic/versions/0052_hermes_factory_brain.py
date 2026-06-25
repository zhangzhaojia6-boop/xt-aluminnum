"""hermes factory brain persistence

Revision ID: 0052_hermes_factory_brain
Revises: 0049_hermes_data_audit
Create Date: 2026-06-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = '0052_hermes_factory_brain'
down_revision = '0049_hermes_data_audit'
branch_labels = None
depends_on = None


TABLES = (
    'hermes_soul_profiles',
    'hermes_long_term_rules',
    'hermes_dingtalk_sampling_rules',
    'hermes_knowledge_units',
    'hermes_codex_construction_runs',
)

json_object_type = sa.JSON().with_variant(JSONB, 'postgresql')


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index['name'] == index_name for index in inspector.get_indexes(table_name))


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def _create_index(inspector: sa.Inspector, table_name: str, column_name: str, *, unique: bool = False) -> None:
    index_name = f'ix_{table_name}_{column_name}'
    if not _has_index(inspector, table_name, index_name):
        op.create_index(index_name, table_name, [column_name], unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'hermes_soul_profiles'):
        op.create_table(
            'hermes_soul_profiles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('profile_key', sa.String(length=128), nullable=False),
            sa.Column('version', sa.String(length=64), nullable=False),
            sa.Column('soul_text', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('profile_key', 'version', name='uq_hermes_soul_profile_key_version'),
        )
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'hermes_soul_profiles'):
        for column_name in ('profile_key', 'version', 'status', 'created_by_id'):
            _create_index(inspector, 'hermes_soul_profiles', column_name)

    if not _has_table(inspector, 'hermes_long_term_rules'):
        op.create_table(
            'hermes_long_term_rules',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('rule_key', sa.String(length=128), nullable=False),
            sa.Column('raw_text', sa.Text(), nullable=False),
            sa.Column('structured_rule', json_object_type, nullable=False),
            sa.Column('scope_payload', json_object_type, nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('risk_level', sa.String(length=16), nullable=False, server_default='low'),
            sa.Column('priority', sa.Integer(), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('confirmed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('source_trace_id', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'hermes_long_term_rules'):
        for column_name, unique in (
            ('rule_key', True),
            ('status', False),
            ('risk_level', False),
            ('created_by_id', False),
            ('confirmed_by_id', False),
            ('source_trace_id', False),
        ):
            _create_index(inspector, 'hermes_long_term_rules', column_name, unique=unique)

    if not _has_table(inspector, 'hermes_dingtalk_sampling_rules'):
        op.create_table(
            'hermes_dingtalk_sampling_rules',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('rule_key', sa.String(length=128), nullable=False),
            sa.Column('channel_key', sa.String(length=128), nullable=False),
            sa.Column('specialist_user_id', sa.String(length=64), nullable=False),
            sa.Column('content_types', json_object_type, nullable=False),
            sa.Column('time_window_payload', json_object_type, nullable=False),
            sa.Column('priority', sa.String(length=32), nullable=False, server_default='normal'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'hermes_dingtalk_sampling_rules'):
        for column_name, unique in (
            ('rule_key', True),
            ('channel_key', False),
            ('specialist_user_id', False),
            ('priority', False),
            ('status', False),
            ('created_by_id', False),
        ):
            _create_index(inspector, 'hermes_dingtalk_sampling_rules', column_name, unique=unique)

    if not _has_table(inspector, 'hermes_knowledge_units'):
        op.create_table(
            'hermes_knowledge_units',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('unit_key', sa.String(length=128), nullable=False),
            sa.Column('layer', sa.String(length=64), nullable=False),
            sa.Column('unit_type', sa.String(length=64), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('metadata_payload', json_object_type, nullable=False),
            sa.Column('verification_payload', json_object_type, nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='candidate'),
            sa.Column('document_id', sa.Integer(), sa.ForeignKey('rag_documents.id'), nullable=True),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('verified_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'hermes_knowledge_units'):
        for column_name, unique in (
            ('unit_key', True),
            ('layer', False),
            ('unit_type', False),
            ('status', False),
            ('document_id', False),
            ('created_by_id', False),
            ('verified_by', False),
        ):
            _create_index(inspector, 'hermes_knowledge_units', column_name, unique=unique)

    if not _has_table(inspector, 'hermes_codex_construction_runs'):
        op.create_table(
            'hermes_codex_construction_runs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('trace_id', sa.String(length=128), nullable=False),
            sa.Column('request_text', sa.Text(), nullable=False),
            sa.Column('construction_type', sa.String(length=32), nullable=False),
            sa.Column('authorization_level', sa.String(length=32), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('payload', json_object_type, nullable=False),
            sa.Column('result_payload', json_object_type, nullable=True),
            sa.Column('requested_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'hermes_codex_construction_runs'):
        for column_name, unique in (
            ('trace_id', True),
            ('construction_type', False),
            ('authorization_level', False),
            ('status', False),
            ('requested_by_id', False),
        ):
            _create_index(inspector, 'hermes_codex_construction_runs', column_name, unique=unique)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    index_map = {
        'hermes_codex_construction_runs': (
            'trace_id',
            'construction_type',
            'authorization_level',
            'status',
            'requested_by_id',
        ),
        'hermes_knowledge_units': (
            'unit_key',
            'layer',
            'unit_type',
            'status',
            'document_id',
            'created_by_id',
            'verified_by',
        ),
        'hermes_dingtalk_sampling_rules': (
            'rule_key',
            'channel_key',
            'specialist_user_id',
            'priority',
            'status',
            'created_by_id',
        ),
        'hermes_long_term_rules': (
            'rule_key',
            'status',
            'risk_level',
            'created_by_id',
            'confirmed_by_id',
            'source_trace_id',
        ),
        'hermes_soul_profiles': (
            'profile_key',
            'version',
            'status',
            'created_by_id',
        ),
    }

    for table_name in reversed(TABLES):
        if not _has_table(inspector, table_name):
            continue
        for column_name in index_map[table_name]:
            _safe_drop_index(f'ix_{table_name}_{column_name}', table_name)
        op.drop_table(table_name)
