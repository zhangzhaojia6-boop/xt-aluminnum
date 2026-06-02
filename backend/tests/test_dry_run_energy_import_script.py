from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path

import pandas as pd

from app.models.energy import EnergyImportRecord
from app.services import energy_service


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / 'scripts' / 'dry_run_energy_import.py'
    spec = importlib.util.spec_from_file_location('dry_run_energy_import', script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_electricity_workbook(path: Path) -> None:
    frame = pd.DataFrame(
        [
            ['各车间能耗统计表（26年5月）', '', '', '', '', '', ''],
            ['车间/日期', '', '1日', '2日', '3日', '4日', '5日'],
            ['铸锭', '', 7900, 7650, 7850, 7650, 7950],
            ['铸二', '', 1200, 1860, 2220, 2040, 1920],
            ['铸五制水房', '', 130, 260, 170, 420, 300],
            [2050, '', 23900, 19740, 25580, 23360, 24180],
            ['热轧', '', 53526, 46176, 40410, 48316, 10314],
            ['拉矫', '', 11048, 10840, 10750, 10630, 11640],
            ['合计', '', 152680, 153880, 141560, 171580, 125320],
        ]
    )
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, header=False, sheet_name='用量')


def _write_gas_workbook(path: Path) -> None:
    meter_frame = pd.DataFrame(
        [
            ['各车间天然气抄表统计表（26年5月）', '', '', '', '', '', '', '', '', '', '', '', ''],
            ['车间/日期', '铸锭', '回收', '铸二', '铸三', '热轧', '', '', '拉矫', '', '北线', '南线', '总表'],
            ['', '', '', '', '', '轧机（东）', '轧机（西）', '锅炉', '退火炉', '锅炉', '', '', ''],
            [5, 9980517, 174827, 4132867, 3368015, 4017200, 4090457, 3948712, 74214566, 7716632, 630842, 1682673, 81743680],
        ]
    )
    frame = pd.DataFrame(
        [
            ['各车间天然气用量统计表（26年5月）', '', '', '', '', '', '', '', '', '', '', '', ''],
            ['车间/日期', '铸锭', '回收', '铸二', '铸三', '热轧', '', '', '拉矫', '', '北线', '南线', '合计'],
            ['', '', '', '', '', '加热炉东', '加热炉西', '锅炉', '退火炉', '锅炉', '', '', ''],
            [1, 27906, 923, 3979, 4239, 5501, 4970, 1102, 1233, 1351, 0, 0, 53162],
            [5, 25673, 1446, 3004, 3993, 0, 0, 344, 880, 1781, 7455, 0, 46519],
        ]
    )
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        meter_frame.to_excel(writer, index=False, header=False, sheet_name='抄表')
        frame.to_excel(writer, index=False, header=False, sheet_name='用量')


def test_daily_energy_dry_run_maps_real_monthly_wide_tables(tmp_path: Path) -> None:
    module = _load_script_module()
    electricity = tmp_path / 'workshop-energy.xlsx'
    gas = tmp_path / 'workshop-gas.xlsx'
    _write_electricity_workbook(electricity)
    _write_gas_workbook(gas)

    payload = module.build_daily_energy_dry_run(
        electricity_file=electricity,
        gas_file=gas,
        report_date=date(2026, 5, 5),
    )

    assert payload['hard_gate_passed'] is True
    assert payload['business_date'] == '2026-05-05'
    assert payload['totals']['electricity_value'] == 56004.0
    assert payload['totals']['gas_value'] == 43130.0
    assert payload['mapping']['ready_rows'] == 12
    assert payload['mapping']['skipped_rows'] == 4
    assert payload['blocking_issues'] == []

    skipped_labels = {row['source_label'] for row in payload['mapping']['rows'] if row['status'] == 'skipped'}
    assert {'铸五制水房', '合计', '回收'} <= skipped_labels


def test_daily_energy_parser_maps_online_annealing_split_labels(tmp_path: Path) -> None:
    from app.services.daily_energy_report_service import parse_workshop_electricity_workbook

    electricity = tmp_path / 'online-energy.xlsx'
    frame = pd.DataFrame(
        [
            ['各车间能耗统计表（26年5月）', '', ''],
            ['车间/日期', '5日', '6日'],
            ['北线', 1200, 0],
            ['园区北线', 800, 0],
        ]
    )
    with pd.ExcelWriter(electricity, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, header=False, sheet_name='用量')

    rows = parse_workshop_electricity_workbook(electricity, report_date=date(2026, 5, 5))
    rows_by_label = {row.source_label: row for row in rows}

    assert rows_by_label['北线'].status == 'success'
    assert rows_by_label['北线'].workshop_code == 'ZXTF-N'
    assert rows_by_label['园区北线'].status == 'success'
    assert rows_by_label['园区北线'].workshop_code == 'ZXTF-P'


def test_daily_energy_gas_parser_does_not_treat_year_26_as_day_26(tmp_path: Path) -> None:
    module = _load_script_module()
    gas = tmp_path / 'workshop-gas-day26.xlsx'

    frame = pd.DataFrame(
        [
            ['各车间天然气用量统计表（26年5月）', '', '', '', '', '', '', '', '', '', '', '', ''],
            ['车间/日期', '铸锭', '回收', '铸二', '铸三', '热轧', '', '', '拉矫', '', '北线', '南线', '合计'],
            ['', '', '', '', '', '加热炉东', '加热炉西', '锅炉', '退火炉', '锅炉', '', '', ''],
            [26, 25763, 1524, 0, 4410, 4754, 4005, 1117, 3550, 1080, 2509, 2033, 50780],
        ]
    )
    with pd.ExcelWriter(gas, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, header=False, sheet_name='用量')

    payload = module.build_daily_energy_dry_run(
        gas_file=gas,
        report_date=date(2026, 5, 26),
    )

    assert payload['hard_gate_passed'] is True
    assert payload['totals']['gas_value'] == 49221.0
    assert payload['mapping']['ready_rows'] == 9


def test_stage_and_promote_daily_energy_batch_writes_summary_records(tmp_path: Path) -> None:
    module = _load_script_module()
    electricity = tmp_path / 'workshop-energy.xlsx'
    gas = tmp_path / 'workshop-gas.xlsx'
    _write_electricity_workbook(electricity)
    _write_gas_workbook(gas)

    db = module._create_dry_run_session()
    try:
        module.seed_real_master_data(db)

        staged = module.stage_daily_energy_import(
            electricity_file=electricity,
            gas_file=gas,
            report_date=date(2026, 5, 5),
            db=db,
            commit=True,
        )

        assert staged['staging_write']['committed'] is True
        assert staged['staging_write']['rows_written'] == 16
        assert staged['staging_write']['energy_record_rows_written'] == 0

        dry_run = module.promote_daily_energy_batch(
            db,
            batch_id=staged['staging_write']['batch_id'],
            commit=False,
        )
        assert dry_run['committed'] is False
        assert dry_run['projected_record_rows'] == 12
        assert db.query(EnergyImportRecord).count() == 0

        promoted = module.promote_daily_energy_batch(
            db,
            batch_id=staged['staging_write']['batch_id'],
            commit=True,
        )
        assert promoted['committed'] is True
        assert promoted['record_rows_written'] == 12

        rows = {row['workshop_code']: row for row in energy_service.get_energy_summary(db, business_date=date(2026, 5, 5))}
        assert rows['ZD']['electricity_value'] == 7950.0
        assert rows['ZD']['gas_value'] == 25673.0
        assert rows['ZR2']['electricity_value'] == 1920.0
        assert rows['ZR2']['gas_value'] == 3004.0
        assert rows['RZ']['electricity_value'] == 10314.0
        assert rows['RZ']['gas_value'] == 344.0
        assert rows['JZ']['electricity_value'] == 11640.0
        assert rows['JZ']['gas_value'] == 2661.0
        assert rows['ZXTF-N']['gas_value'] == 7455.0

        duplicate = module.promote_daily_energy_batch(
            db,
            batch_id=staged['staging_write']['batch_id'],
            commit=True,
        )
        assert duplicate['committed'] is False
        assert duplicate['record_rows_written'] == 0
        assert duplicate['blocking_issues'][0]['code'] == 'duplicate_daily_energy_record'
    finally:
        db.close()
