from pathlib import Path
from types import SimpleNamespace

import app.models  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.executive import (
    CostDailyResult,
    CostMonthlyRollup,
    CostPriceMaster,
    CostVarianceRecord,
    CostWorkshopStrategy,
)
from app.services import executive_service


REPO_ROOT = Path(__file__).resolve().parents[2]


def _table(name: str):
    return Base.metadata.tables[name]


def _column_names(name: str) -> set[str]:
    return set(_table(name).columns.keys())


def test_cost_strategy_contract_tables_are_registered_in_backend_metadata() -> None:
    expected_tables = {
        'cost_price_master',
        'cost_workshop_strategy',
        'cost_daily_result',
        'cost_monthly_rollup',
        'cost_variance_record',
    }

    assert expected_tables.issubset(Base.metadata.tables)
    assert {
        'item_code',
        'item_name',
        'unit',
        'unit_price',
        'effective_from',
        'effective_to',
        'workshop_scope',
        'process_scope',
        'source_note',
    }.issubset(_column_names('cost_price_master'))
    assert {
        'workshop_code',
        'strategy_code',
        'enabled',
        'effective_from',
        'caliber',
        'config_snapshot',
    }.issubset(_column_names('cost_workshop_strategy'))
    assert {
        'business_date',
        'workshop_code',
        'strategy_code',
        'total_cost',
        'output_ton_cost',
        'throughput_ton_cost',
        'caliber',
        'breakdown_count',
        'process_count',
    }.issubset(_column_names('cost_daily_result'))
    assert {
        'month',
        'workshop_code',
        'strategy_code',
        'month_total_cost',
        'month_output_ton_cost',
        'month_throughput_ton_cost',
        'source',
    }.issubset(_column_names('cost_monthly_rollup'))
    assert {
        'business_date',
        'workshop_code',
        'variance_type',
        'baseline_value',
        'current_value',
        'diff_value',
        'status',
    }.issubset(_column_names('cost_variance_record'))


def test_cost_strategy_tables_have_business_keys_and_seed_migration() -> None:
    assert 'uq_cost_price_master_version' in {constraint.name for constraint in _table('cost_price_master').constraints}
    assert 'uq_cost_workshop_strategy_version' in {
        constraint.name for constraint in _table('cost_workshop_strategy').constraints
    }
    assert 'uq_cost_daily_result_version' in {constraint.name for constraint in _table('cost_daily_result').constraints}
    assert 'uq_cost_monthly_rollup_version' in {
        constraint.name for constraint in _table('cost_monthly_rollup').constraints
    }
    assert 'uq_cost_variance_record_version' in {
        constraint.name for constraint in _table('cost_variance_record').constraints
    }

    migration = (REPO_ROOT / 'backend/alembic/versions/0028_cost_strategy_tables.py').read_text(encoding='utf-8')
    for table_name in [
        'cost_price_master',
        'cost_workshop_strategy',
        'cost_daily_result',
        'cost_monthly_rollup',
        'cost_variance_record',
    ]:
        assert table_name in migration
    for seed_code in ['ELECTRICITY', 'NATURAL_GAS', 'ROLLING_OIL', 'AIR_ELECTRICITY']:
        assert seed_code in migration


def _build_cost_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cost-contract.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            CostPriceMaster.__table__,
            CostWorkshopStrategy.__table__,
            CostDailyResult.__table__,
            CostMonthlyRollup.__table__,
            CostVarianceRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _snapshot_payload(total_cost: float = 1240.5) -> dict:
    return {
        'table_models': {
            'cost_price_master': [
                {
                    'item_code': 'ELECTRICITY',
                    'item_name': '电费',
                    'unit': 'kWh',
                    'unit_price': 0.8,
                    'effective_from': '2026-04-01',
                    'effective_to': '',
                    'workshop_scope': 'ALL',
                    'process_scope': 'ALL',
                    'source_note': '大推进.md 默认单价',
                }
            ],
            'cost_workshop_strategy': [
                {
                    'workshop_code': 'LJ',
                    'strategy_code': 'TENSION_LEVELING_MAIN_PLUS_AUX',
                    'enabled': True,
                    'effective_from': '2026-05-12',
                    'caliber': 'output',
                    'config_snapshot': {'outputTon': 12.5, 'processCount': 2},
                }
            ],
            'cost_daily_result': [
                {
                    'business_date': '2026-05-12',
                    'workshop_code': 'LJ',
                    'strategy_code': 'TENSION_LEVELING_MAIN_PLUS_AUX',
                    'total_cost': total_cost,
                    'output_ton_cost': 99.24,
                    'throughput_ton_cost': 93.18,
                    'caliber': 'output',
                    'breakdown_count': 4,
                    'process_count': 2,
                }
            ],
            'cost_monthly_rollup': [
                {
                    'month': '2026-05',
                    'workshop_code': 'LJ',
                    'strategy_code': 'TENSION_LEVELING_MAIN_PLUS_AUX',
                    'month_total_cost': total_cost,
                    'month_output_ton_cost': 99.24,
                    'month_throughput_ton_cost': 93.18,
                    'source': 'frontend_strategy_snapshot',
                }
            ],
            'cost_variance_record': [
                {
                    'business_date': '2026-05-12',
                    'workshop_code': 'LJ',
                    'variance_type': 'OUTPUT_VS_THROUGHPUT',
                    'baseline_value': 93.18,
                    'current_value': 99.24,
                    'diff_value': 6.06,
                    'status': 'normal',
                }
            ],
        }
    }


def test_persist_cost_strategy_snapshot_upserts_all_contract_tables(tmp_path) -> None:
    Session = _build_cost_session(tmp_path)

    with Session() as db:
        result = executive_service.persist_cost_strategy_snapshot(db, table_models=_snapshot_payload()['table_models'])
        db.commit()

        assert result['saved'] == {
            'cost_price_master': 1,
            'cost_workshop_strategy': 1,
            'cost_daily_result': 1,
            'cost_monthly_rollup': 1,
            'cost_variance_record': 1,
        }
        assert db.execute(select(CostPriceMaster)).scalar_one().item_code == 'ELECTRICITY'
        assert db.execute(select(CostWorkshopStrategy)).scalar_one().config_snapshot['outputTon'] == 12.5
        assert float(db.execute(select(CostDailyResult)).scalar_one().total_cost) == 1240.5

        second = executive_service.persist_cost_strategy_snapshot(
            db,
            table_models=_snapshot_payload(total_cost=1300.0)['table_models'],
        )
        db.commit()

        assert second['saved']['cost_daily_result'] == 1
        assert len(db.execute(select(CostDailyResult)).scalars().all()) == 1
        assert float(db.execute(select(CostDailyResult)).scalar_one().total_cost) == 1300.0


def test_cost_strategy_snapshot_route_requires_admin_and_persists(monkeypatch) -> None:
    calls = []
    commits = []
    fake_db = SimpleNamespace(commit=lambda: commits.append(True))

    def fake_get_db():
        yield fake_db

    def fake_admin():
        return SimpleNamespace(id=1, role='admin', data_scope_type='all')

    def fake_persist(db, *, table_models):
        calls.append((db, table_models))
        return {'saved': {name: len(rows) for name, rows in table_models.items()}}

    monkeypatch.setattr(executive_service, 'persist_cost_strategy_snapshot', fake_persist)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_admin
    try:
        response = TestClient(app).post('/api/v1/executive/cost-strategy-snapshots', json=_snapshot_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['saved']['cost_daily_result'] == 1
    assert calls == [(fake_db, _snapshot_payload()['table_models'])]
    assert commits == [True]


def test_cost_strategy_snapshot_route_accepts_frontend_table_models_alias(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield SimpleNamespace(commit=lambda: None)

    def fake_admin():
        return SimpleNamespace(id=1, role='admin', data_scope_type='all')

    def fake_persist(db, *, table_models):
        calls.append(table_models)
        return {'saved': {name: len(rows) for name, rows in table_models.items()}}

    payload = {'tableModels': _snapshot_payload()['table_models']}
    monkeypatch.setattr(executive_service, 'persist_cost_strategy_snapshot', fake_persist)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_admin
    try:
        response = TestClient(app).post('/api/v1/executive/cost-strategy-snapshots', json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['saved']['cost_price_master'] == 1
    assert calls == [_snapshot_payload()['table_models']]


def test_cost_strategy_snapshot_route_blocks_non_admin(monkeypatch) -> None:
    def fake_get_db():
        yield SimpleNamespace()

    def fake_manager():
        return SimpleNamespace(id=2, role='manager', data_scope_type='all', is_manager=True)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_manager
    try:
        response = TestClient(app).post('/api/v1/executive/cost-strategy-snapshots', json=_snapshot_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
