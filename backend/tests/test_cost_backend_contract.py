from pathlib import Path

import app.models  # noqa: F401
from app.database import Base


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
