from importlib import util as importlib_util
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, Column, Integer, create_engine, inspect
from sqlalchemy.dialects import postgresql

from app.models import Base, User


MIGRATION_PATH = Path(__file__).resolve().parents[1] / 'alembic' / 'versions' / '0049_hermes_data_audit.py'


def _load_migration_module():
    spec = importlib_util.spec_from_file_location('migration_0049_hermes_data_audit', MIGRATION_PATH)
    module = importlib_util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_app_models_exports_hermes_data_audit_models() -> None:
    from app.models import HermesCorrectionAction, HermesDataAuditRun

    assert HermesDataAuditRun.__tablename__ == 'hermes_data_audit_runs'
    assert HermesCorrectionAction.__tablename__ == 'hermes_correction_actions'


def test_hermes_data_audit_tables_include_required_columns_and_indexes() -> None:
    from app.models import HermesCorrectionAction, HermesDataAuditRun

    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine, tables=[User.__table__, HermesDataAuditRun.__table__, HermesCorrectionAction.__table__])

    inspector = inspect(engine)

    run_columns = {column['name'] for column in inspector.get_columns('hermes_data_audit_runs')}
    action_columns = {column['name'] for column in inspector.get_columns('hermes_correction_actions')}

    assert {
        'id',
        'run_key',
        'business_date',
        'status',
        'source_status',
        'source_errors',
        'mes_snapshot',
        'hub_snapshot',
        'output_skill_snapshot',
        'diffs',
        'suggested_actions',
        'match_rate',
        'created_by_id',
        'started_at',
        'completed_at',
        'created_at',
        'updated_at',
    } <= run_columns
    assert {
        'id',
        'audit_run_id',
        'idempotency_key',
        'action_type',
        'risk_level',
        'target_table',
        'target_key',
        'field_name',
        'before_value',
        'after_value',
        'evidence',
        'status',
        'applied_by_id',
        'applied_at',
        'rollback_status',
        'rollback_payload',
        'created_at',
        'updated_at',
    } <= action_columns

    run_indexes = {index['name']: tuple(index['column_names']) for index in inspector.get_indexes('hermes_data_audit_runs')}
    action_indexes = {index['name']: tuple(index['column_names']) for index in inspector.get_indexes('hermes_correction_actions')}

    assert ('business_date',) in run_indexes.values()
    assert ('status',) in run_indexes.values()
    assert ('run_key',) in run_indexes.values()
    assert ('created_by_id',) in run_indexes.values()
    assert ('audit_run_id',) in action_indexes.values()
    assert ('idempotency_key',) in action_indexes.values()
    assert ('id',) not in run_indexes.values()
    assert ('id',) not in action_indexes.values()


def test_hermes_correction_action_audit_run_fk_points_to_audit_runs() -> None:
    from app.models import HermesCorrectionAction, HermesDataAuditRun

    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine, tables=[User.__table__, HermesDataAuditRun.__table__, HermesCorrectionAction.__table__])

    inspector = inspect(engine)
    foreign_keys = inspector.get_foreign_keys('hermes_correction_actions')

    assert any(
        fk['referred_table'] == 'hermes_data_audit_runs'
        and fk['constrained_columns'] == ['audit_run_id']
        and fk['referred_columns'] == ['id']
        for fk in foreign_keys
    )


def test_hermes_data_audit_migration_uses_jsonb_payload_columns_for_postgres(monkeypatch) -> None:
    migration = _load_migration_module()
    created_tables: dict[str, tuple] = {}

    class _Inspector:
        def has_table(self, _table_name: str) -> bool:
            return False

        def get_indexes(self, _table_name: str) -> list[dict]:
            return []

    monkeypatch.setattr(migration.op, 'get_bind', lambda: object())
    monkeypatch.setattr(migration.sa, 'inspect', lambda _bind: _Inspector())
    monkeypatch.setattr(migration.op, 'create_index', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op,
        'create_table',
        lambda table_name, *columns, **kwargs: created_tables.setdefault(table_name, columns),
    )

    migration.upgrade()

    run_columns = {column.name: column for column in created_tables['hermes_data_audit_runs']}
    action_columns = {column.name: column for column in created_tables['hermes_correction_actions']}

    for column_name in (
        'source_status',
        'source_errors',
        'mes_snapshot',
        'hub_snapshot',
        'output_skill_snapshot',
        'diffs',
        'suggested_actions',
    ):
        assert str(run_columns[column_name].type.compile(dialect=postgresql.dialect())) == 'JSONB'

    for column_name in ('before_value', 'after_value', 'evidence', 'rollback_payload'):
        assert str(action_columns[column_name].type.compile(dialect=postgresql.dialect())) == 'JSONB'


def test_hermes_data_audit_migration_upgrade_and_downgrade_on_sqlite(tmp_path) -> None:
    migration = _load_migration_module()
    engine = create_engine(f"sqlite:///{(tmp_path / 'hermes_data_audit_migration.db').as_posix()}", future=True)

    metadata = MetaData()
    Table('users', metadata, Column('id', Integer, primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as conn:
        original_op = migration.op
        migration.op = Operations(MigrationContext.configure(conn))
        try:
            migration.upgrade()

            inspector = inspect(conn)
            assert inspector.has_table('hermes_data_audit_runs')
            assert inspector.has_table('hermes_correction_actions')

            run_columns = {column['name'] for column in inspector.get_columns('hermes_data_audit_runs')}
            action_columns = {column['name'] for column in inspector.get_columns('hermes_correction_actions')}
            assert {'id', 'run_key', 'business_date', 'status', 'source_status', 'created_by_id'} <= run_columns
            assert {'id', 'audit_run_id', 'idempotency_key', 'status', 'rollback_status'} <= action_columns

            run_indexes = {index['name']: tuple(index['column_names']) for index in inspector.get_indexes('hermes_data_audit_runs')}
            action_indexes = {index['name']: tuple(index['column_names']) for index in inspector.get_indexes('hermes_correction_actions')}
            assert ('run_key',) in run_indexes.values()
            assert ('business_date',) in run_indexes.values()
            assert ('status',) in run_indexes.values()
            assert ('created_by_id',) in run_indexes.values()
            assert ('audit_run_id',) in action_indexes.values()
            assert ('idempotency_key',) in action_indexes.values()

            migration.downgrade()

            inspector = inspect(conn)
            assert not inspector.has_table('hermes_correction_actions')
            assert not inspector.has_table('hermes_data_audit_runs')
        finally:
            migration.op = original_op
