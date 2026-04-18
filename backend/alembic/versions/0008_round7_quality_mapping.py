"""round7 quality gate and mapping

Revision ID: 0008_round7
Revises: 0007_round6
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0008_round7'
down_revision = '0007_round6'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _has_fk(inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {item.get('name') for item in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'import_batches'):
        if not _has_column(inspector, 'import_batches', 'mapping_template_code'):
            op.add_column('import_batches', sa.Column('mapping_template_code', sa.String(length=64), nullable=True))
        if not _has_column(inspector, 'import_batches', 'source_type'):
            op.add_column('import_batches', sa.Column('source_type', sa.String(length=64), nullable=True))
            op.create_index('ix_import_batches_source_type', 'import_batches', ['source_type'], unique=False)
        if not _has_column(inspector, 'import_batches', 'quality_status'):
            op.add_column('import_batches', sa.Column('quality_status', sa.String(length=16), nullable=False, server_default='pending_check'))
        if not _has_column(inspector, 'import_batches', 'parsed_successfully'):
            op.add_column('import_batches', sa.Column('parsed_successfully', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    if _has_table(inspector, 'field_mapping_templates'):
        if not _has_column(inspector, 'field_mapping_templates', 'source_type'):
            op.add_column('field_mapping_templates', sa.Column('source_type', sa.String(length=64), nullable=True))
            op.create_index('ix_field_mapping_templates_source_type', 'field_mapping_templates', ['source_type'], unique=False)

    if _has_table(inspector, 'daily_reports'):
        if not _has_column(inspector, 'daily_reports', 'quality_gate_status'):
            op.add_column('daily_reports', sa.Column('quality_gate_status', sa.String(length=16), nullable=False, server_default='pending'))
        if not _has_column(inspector, 'daily_reports', 'quality_gate_summary'):
            op.add_column('daily_reports', sa.Column('quality_gate_summary', sa.Text(), nullable=True))
        if not _has_column(inspector, 'daily_reports', 'delivery_ready'):
            op.add_column('daily_reports', sa.Column('delivery_ready', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    if not _has_table(inspector, 'master_code_aliases'):
        op.create_table(
            'master_code_aliases',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('entity_type', sa.String(length=32), nullable=False),
            sa.Column('canonical_code', sa.String(length=64), nullable=False),
            sa.Column('alias_code', sa.String(length=64), nullable=True),
            sa.Column('alias_name', sa.String(length=128), nullable=True),
            sa.Column('source_type', sa.String(length=64), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint('entity_type', 'alias_code', 'source_type', name='uq_master_code_aliases_code'),
        )
        op.create_index('ix_master_code_aliases_entity_type', 'master_code_aliases', ['entity_type'], unique=False)
        op.create_index('ix_master_code_aliases_canonical_code', 'master_code_aliases', ['canonical_code'], unique=False)
        op.create_index('ix_master_code_aliases_alias_code', 'master_code_aliases', ['alias_code'], unique=False)
        op.create_index('ix_master_code_aliases_source_type', 'master_code_aliases', ['source_type'], unique=False)

    if not _has_table(inspector, 'data_quality_issues'):
        op.create_table(
            'data_quality_issues',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('issue_type', sa.String(length=32), nullable=False),
            sa.Column('source_type', sa.String(length=64), nullable=True),
            sa.Column('dimension_key', sa.String(length=128), nullable=True),
            sa.Column('field_name', sa.String(length=64), nullable=True),
            sa.Column('issue_level', sa.String(length=16), nullable=False, server_default='warning'),
            sa.Column('issue_desc', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='open'),
            sa.Column('resolved_by', sa.Integer(), nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolve_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_data_quality_issues_business_date', 'data_quality_issues', ['business_date'], unique=False)
        op.create_index('ix_data_quality_issues_issue_type', 'data_quality_issues', ['issue_type'], unique=False)
        op.create_index('ix_data_quality_issues_issue_level', 'data_quality_issues', ['issue_level'], unique=False)
        op.create_index('ix_data_quality_issues_status', 'data_quality_issues', ['status'], unique=False)
        op.create_index('ix_data_quality_issues_dimension_key', 'data_quality_issues', ['dimension_key'], unique=False)
        op.create_index('ix_data_quality_issues_field_name', 'data_quality_issues', ['field_name'], unique=False)
        op.create_index('ix_data_quality_issues_source_type', 'data_quality_issues', ['source_type'], unique=False)
        if not _has_fk(inspector, 'data_quality_issues', 'fk_data_quality_issues_resolved_by'):
            op.create_foreign_key(
                'fk_data_quality_issues_resolved_by',
                'data_quality_issues',
                'users',
                ['resolved_by'],
                ['id'],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'data_quality_issues'):
        for index_name in [
            'ix_data_quality_issues_source_type',
            'ix_data_quality_issues_field_name',
            'ix_data_quality_issues_dimension_key',
            'ix_data_quality_issues_status',
            'ix_data_quality_issues_issue_level',
            'ix_data_quality_issues_issue_type',
            'ix_data_quality_issues_business_date',
        ]:
            if _has_index(inspector, 'data_quality_issues', index_name):
                op.drop_index(index_name, table_name='data_quality_issues')
        if _has_fk(inspector, 'data_quality_issues', 'fk_data_quality_issues_resolved_by'):
            op.drop_constraint('fk_data_quality_issues_resolved_by', 'data_quality_issues', type_='foreignkey')
        op.drop_table('data_quality_issues')

    if _has_table(inspector, 'master_code_aliases'):
        for index_name in [
            'ix_master_code_aliases_source_type',
            'ix_master_code_aliases_alias_code',
            'ix_master_code_aliases_canonical_code',
            'ix_master_code_aliases_entity_type',
        ]:
            if _has_index(inspector, 'master_code_aliases', index_name):
                op.drop_index(index_name, table_name='master_code_aliases')
        op.drop_table('master_code_aliases')

    if _has_table(inspector, 'daily_reports'):
        for column_name in ['delivery_ready', 'quality_gate_summary', 'quality_gate_status']:
            if _has_column(inspector, 'daily_reports', column_name):
                op.drop_column('daily_reports', column_name)

    if _has_table(inspector, 'field_mapping_templates'):
        if _has_index(inspector, 'field_mapping_templates', 'ix_field_mapping_templates_source_type'):
            op.drop_index('ix_field_mapping_templates_source_type', table_name='field_mapping_templates')
        if _has_column(inspector, 'field_mapping_templates', 'source_type'):
            op.drop_column('field_mapping_templates', 'source_type')

    if _has_table(inspector, 'import_batches'):
        for column_name in ['parsed_successfully', 'quality_status', 'source_type', 'mapping_template_code']:
            if _has_column(inspector, 'import_batches', column_name):
                op.drop_column('import_batches', column_name)
        if _has_index(inspector, 'import_batches', 'ix_import_batches_source_type'):
            op.drop_index('ix_import_batches_source_type', table_name='import_batches')
