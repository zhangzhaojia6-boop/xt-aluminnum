from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path

import pandas as pd
from sqlalchemy import func

from app.models.imports import ImportBatch, ImportRow
from app.models.production import ShiftProductionData


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / 'scripts' / 'dry_run_daily_production_import.py'
    spec = importlib.util.spec_from_file_location('dry_run_daily_production_import', script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_daily_workbook(path: Path, *, cold_rolling_output: float = 224.54) -> None:
    frame = pd.DataFrame([
        ['生产系统综合日报表2026年5月3日', '', '', '', '', '', '', '', '', '', ''],
        ['', '', '', '', '', '', '', '', '', '', ''],
        ['车间', '项目', '投入', '月累计投入', '产出', '月累计产出', '', '废料', '月累计废料', '成品率', '指标'],
        ['铸锭', '', 320.0, 1000.0, 314.19, 900.0, '', 5.81, 20.0, 98.2, 97.0],
        ['冷轧', '1650', 240.0, 800.0, cold_rolling_output, 700.0, '', 15.46, 35.0, 93.5, 94.0],
        ['', '2050', 92.0, 500.0, 85.13, 450.0, '', 6.87, 25.0, 92.5, 94.0],
        ['合计', '', '', '', '', '', '', '', '', '', ''],
    ])
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, header=False, sheet_name='综合报表')


def _write_zero_daily_workbook(path: Path) -> None:
    frame = pd.DataFrame(
        [
            ['生产系统综合日报表2026年5月5日', '', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', '', ''],
            ['车间', '项目', '投入', '月累计投入', '产出', '月累计产出', '', '废料', '月累计废料', '成品率', '指标'],
            ['铸锭', '', 0, 1000.0, 0, 900.0, '', 0, 20.0, 0, 97.0],
            ['合计', '', '', '', '', '', '', '', '', '', ''],
        ]
    )
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, header=False, sheet_name='综合报表')


def test_dry_run_daily_production_import_uses_locked_date_and_real_master_mapping(tmp_path: Path) -> None:
    module = _load_script_module()
    workbook = tmp_path / 'daily.xlsx'
    _write_daily_workbook(workbook)

    payload = module.build_daily_production_dry_run(
        workbook,
        report_date=date(2026, 5, 5),
        year_hint=2026,
    )

    assert payload['hard_gate_passed'] is True
    assert payload['source']['file_name'] == 'daily.xlsx'
    assert payload['business_date'] == '2026-05-05'
    assert payload['parse']['sheet_count'] == 1
    assert payload['parse']['quality_status'] == 'warning'
    assert [item['code'] for item in payload['parse']['issues']] == ['stale_workbook_report_date']
    assert payload['totals']['daily_output_tons'] == 623.86
    assert payload['mapping']['total_rows'] == 3
    assert payload['mapping']['ready_rows'] == 3
    assert payload['mapping']['unresolved_rows'] == 0
    assert payload['mapping']['needs_equipment_mapping_rows'] == 0
    assert payload['mapping']['equipment_bound_rows'] == 2
    assert payload['mapping']['workshop_only_rows'] == 1

    rows = {(row['workshop_label'], row['project_label']): row for row in payload['mapping']['rows']}
    assert rows[('铸锭', None)]['workshop_code'] == 'ZD'
    assert rows[('冷轧', '1650')]['equipment_code'] == 'LZ1650-1'
    assert rows[('冷轧', '2050')]['equipment_code'] == 'LZ2050-1'


def test_dry_run_daily_production_import_blocks_hard_scale_values(tmp_path: Path) -> None:
    module = _load_script_module()
    workbook = tmp_path / 'daily.xlsx'
    _write_daily_workbook(workbook, cold_rolling_output=120460.0)

    payload = module.build_daily_production_dry_run(
        workbook,
        report_date=date(2026, 5, 5),
        year_hint=2026,
    )

    assert payload['hard_gate_passed'] is False
    assert payload['parse']['quality_status'] == 'blocked'
    assert 'hard_block_kg_as_tons' in [item['code'] for item in payload['parse']['issues']]


def test_stage_daily_production_import_commits_locked_date_without_production_facts(tmp_path: Path) -> None:
    module = _load_script_module()
    workbook = tmp_path / 'daily.xlsx'
    _write_daily_workbook(workbook)
    db = module._create_dry_run_session()
    try:
        module.seed_real_master_data(db)

        payload = module.stage_daily_production_import(
            workbook,
            report_date=date(2026, 5, 5),
            year_hint=2026,
            db=db,
            commit=True,
        )

        assert payload['hard_gate_passed'] is True
        assert payload['staging_write'] == {
            'committed': True,
            'batch_id': 1,
            'rows_written': 1,
            'production_fact_rows_written': 0,
        }
        batch = db.query(ImportBatch).one()
        row = db.query(ImportRow).filter(ImportRow.batch_id == batch.id).one()
        assert batch.import_type == 'daily_production_report'
        assert batch.source_type == 'daily_production_report_locked'
        assert batch.status == 'completed'
        assert row.mapped_data['business_date'] == '2026-05-05'
        assert row.mapped_data['quality_status'] == 'warning'
        assert db.query(func.count(ShiftProductionData.id)).scalar() == 0
    finally:
        db.close()


def test_promote_daily_production_batch_writes_confirmed_ton_facts(tmp_path: Path) -> None:
    module = _load_script_module()
    workbook = tmp_path / 'daily.xlsx'
    _write_daily_workbook(workbook)
    db = module._create_dry_run_session()
    try:
        from app.services.bootstrap import seed_shift_configs

        seed_shift_configs(db)
        module.seed_real_master_data(db)
        staged = module.stage_daily_production_import(
            workbook,
            report_date=date(2026, 5, 5),
            year_hint=2026,
            db=db,
            commit=True,
        )

        payload = module.promote_daily_production_batch(
            db,
            batch_id=staged['staging_write']['batch_id'],
            shift_code='A',
            duplicate_strategy='reject',
            commit=False,
        )

        assert payload['committed'] is False
        assert payload['fact_rows_written'] == 0
        assert payload['total_output_tons'] == 0.0
        assert payload['projected_fact_rows'] == 3
        assert payload['projected_output_tons'] == 623.86
        assert payload['shift_code'] == 'A'
        assert db.query(ShiftProductionData).count() == 0

        payload = module.promote_daily_production_batch(
            db,
            batch_id=staged['staging_write']['batch_id'],
            shift_code='A',
            duplicate_strategy='reject',
            commit=True,
        )

        assert payload['committed'] is True
        assert payload['fact_rows_written'] == 3
        assert payload['total_output_tons'] == 623.86
        assert payload['projected_fact_rows'] == 3
        assert payload['projected_output_tons'] == 623.86
        facts = db.query(ShiftProductionData).order_by(ShiftProductionData.output_weight.desc()).all()
        assert [float(item.output_weight or 0) for item in facts] == [314.19, 224.54, 85.13]
        assert {item.data_source for item in facts} == {'daily_production_report'}
        assert {item.data_status for item in facts} == {'confirmed'}
        assert {item.import_batch_id for item in facts} == {staged['staging_write']['batch_id']}
    finally:
        db.close()


def test_promote_daily_production_batch_preserves_explicit_zero_fact(tmp_path: Path) -> None:
    module = _load_script_module()
    workbook = tmp_path / 'daily-zero.xlsx'
    _write_zero_daily_workbook(workbook)
    db = module._create_dry_run_session()
    try:
        from app.services.bootstrap import seed_shift_configs

        seed_shift_configs(db)
        module.seed_real_master_data(db)
        staged = module.stage_daily_production_import(
            workbook,
            report_date=date(2026, 5, 5),
            year_hint=2026,
            db=db,
            commit=True,
        )
        promoted = module.promote_daily_production_batch(
            db,
            batch_id=staged['staging_write']['batch_id'],
            shift_code='A',
            duplicate_strategy='reject',
            commit=True,
        )

        assert promoted['committed'] is True
        assert promoted['fact_rows_written'] == 1
        assert promoted['total_output_tons'] == 0.0
        fact = db.query(ShiftProductionData).one()
        assert float(fact.input_weight) == 0.0
        assert float(fact.output_weight) == 0.0
        assert float(fact.scrap_weight) == 0.0
    finally:
        db.close()


def test_stage_daily_production_import_rolls_back_when_gate_fails(tmp_path: Path) -> None:
    module = _load_script_module()
    workbook = tmp_path / 'daily.xlsx'
    _write_daily_workbook(workbook, cold_rolling_output=120460.0)
    db = module._create_dry_run_session()
    try:
        module.seed_real_master_data(db)

        payload = module.stage_daily_production_import(
            workbook,
            report_date=date(2026, 5, 5),
            year_hint=2026,
            db=db,
            commit=True,
        )

        assert payload['hard_gate_passed'] is False
        assert payload['staging_write']['committed'] is False
        assert db.query(func.count(ImportBatch.id)).scalar() == 0
        assert db.query(func.count(ImportRow.id)).scalar() == 0
        assert db.query(func.count(ShiftProductionData.id)).scalar() == 0
    finally:
        db.close()
