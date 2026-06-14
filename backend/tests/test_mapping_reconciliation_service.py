from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.mes import MesWorkshopProcessRecord
from app.services.mapping_reconciliation_service import (
    MappingFieldSpec,
    build_system_mapping_rows,
    compare_mapping_rows,
    parse_output_skill_reference_file,
    propose_rules,
)


FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'output_skill_mapping_sample.json'


def test_compare_mapping_rows_converts_kg_to_tons_and_reports_match_rate() -> None:
    reference_rows = [
        {
            'business_date': '2026-06-13',
            'workshop': '精整',
            'shift': '长白班',
            'output_tons': 12.5,
        }
    ]
    system_rows = [
        {
            'business_date': '2026-06-13',
            'workshop': '精整车间',
            'shift': '白班',
            'output_kg': 12500,
        }
    ]

    result = compare_mapping_rows(
        reference_rows=reference_rows,
        system_rows=system_rows,
        fields=[
            MappingFieldSpec(
                metric='output',
                reference_field='output_tons',
                system_field='output_kg',
                reference_unit='ton',
                system_unit='kg',
                tolerance=0.001,
                weight=30,
            )
        ],
        dimension_aliases={'workshop': {'精整车间': '精整'}, 'shift': {'白班': '长白班'}},
    )

    assert result.total_fields == 1
    assert result.matched_fields == 1
    assert result.overall_match_rate == 100
    assert result.differences == []


def test_output_skill_mapping_fixture_matches_after_alias_and_unit_normalization() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))

    result = compare_mapping_rows(
        reference_rows=payload['reference_rows'],
        system_rows=payload['system_rows'],
        fields=[MappingFieldSpec(**item) for item in payload['fields']],
        dimension_aliases=payload['dimension_aliases'],
    )

    assert result.total_fields == 2
    assert result.matched_fields == 2
    assert result.field_match_rates == {'output': 100, 'energy': 100}
    assert result.differences == []


def test_compare_mapping_rows_explains_value_diff_and_missing_rows() -> None:
    reference_rows = [
        {
            'business_date': '2026-06-13',
            'workshop': '拉矫',
            'shift': '小夜班',
            'energy_kwh': 1800,
        },
        {
            'business_date': '2026-06-13',
            'workshop': '园区剪切',
            'shift': '小夜班',
            'energy_kwh': 900,
        },
    ]
    system_rows = [
        {
            'business_date': '2026-06-13',
            'workshop': '拉矫车间',
            'shift': '小夜',
            'electricity_kwh': 1760,
        }
    ]

    result = compare_mapping_rows(
        reference_rows=reference_rows,
        system_rows=system_rows,
        fields=[
            MappingFieldSpec(
                metric='energy',
                reference_field='energy_kwh',
                system_field='electricity_kwh',
                reference_unit='kwh',
                system_unit='kwh',
                tolerance=5,
                weight=15,
            )
        ],
        dimension_aliases={'workshop': {'拉矫车间': '拉矫'}, 'shift': {'小夜': '小夜班'}},
    )

    assert result.overall_match_rate == 0
    assert [item.reason_code for item in result.differences] == ['value_diff', 'missing_system_row']
    assert result.differences[0].reference_value == 1800
    assert result.differences[0].system_value == 1760
    assert result.differences[0].suggested_rule == '检查 energy 字段口径、单位或时间范围。'
    assert result.differences[1].dimension['workshop'] == '园区剪切'


def test_propose_rules_is_dry_run_and_does_not_mutate_source_rows() -> None:
    reference_rows = [
        {
            'business_date': '2026-06-13',
            'workshop': '在线退火',
            'shift': '大夜班',
            'output_tons': 20,
        }
    ]
    system_rows = [
        {
            'business_date': '2026-06-13',
            'workshop': '新厂在线退火',
            'shift': '第一班',
            'output_tons': 20,
        }
    ]
    before_reference = deepcopy(reference_rows)
    before_system = deepcopy(system_rows)

    result = compare_mapping_rows(
        reference_rows=reference_rows,
        system_rows=system_rows,
        fields=[
            MappingFieldSpec(
                metric='output',
                reference_field='output_tons',
                system_field='output_tons',
                reference_unit='ton',
                system_unit='ton',
                tolerance=0.001,
                weight=30,
            )
        ],
        dimension_aliases={},
    )
    proposals = propose_rules(result.differences)

    assert [item.reason_code for item in result.differences] == ['missing_system_row', 'extra_system_row']
    assert proposals == [
        {
            'rule_type': 'alias_candidate',
            'field': 'workshop',
            'reference_value': '在线退火',
            'system_value': '新厂在线退火',
            'confidence': 'manual_review',
            'dry_run': True,
        },
        {
            'rule_type': 'alias_candidate',
            'field': 'shift',
            'reference_value': '大夜班',
            'system_value': '第一班',
            'confidence': 'manual_review',
            'dry_run': True,
        },
    ]
    assert reference_rows == before_reference
    assert system_rows == before_system


def test_parse_output_skill_text_file_extracts_business_metrics(tmp_path) -> None:
    report = tmp_path / '2026-06-13-daily.txt'
    report.write_text(
        '2026年6月13日 生产日报\n'
        '精整 长白班 产量 12.5 吨 能耗 1800 度 废料 0.2 吨\n'
        '拉矫 小夜班 下机量 8000 kg 能耗 950 kWh\n',
        encoding='utf-8',
    )

    result = parse_output_skill_reference_file(report)

    assert result['status'] == 'parsed'
    assert result['source_type'] == 'output_skill_text'
    assert result['rows'] == [
        {
            'business_date': '2026-06-13',
            'workshop': '精整',
            'shift': '长白班',
            'output_tons': 12.5,
            'energy_kwh': 1800.0,
            'scrap_tons': 0.2,
            'source_file': str(report),
            'source_type': 'output_skill_text',
        },
        {
            'business_date': '2026-06-13',
            'workshop': '拉矫',
            'shift': '小夜班',
            'output_tons': 8.0,
            'energy_kwh': 950.0,
            'source_file': str(report),
            'source_type': 'output_skill_text',
        },
    ]


def test_parse_output_skill_xlsx_file_normalizes_common_columns(tmp_path) -> None:
    from openpyxl import Workbook

    report = tmp_path / 'mapping.xlsx'
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['日期', '车间', '班次', '产量(吨)', '能耗(kWh)', '废料(吨)'])
    sheet.append(['2026-06-13', '园区剪切', '长白班', 9.75, 1200, 0.12])
    workbook.save(report)

    result = parse_output_skill_reference_file(report)

    assert result['status'] == 'parsed'
    assert result['source_type'] == 'output_skill_excel'
    assert result['rows'] == [
        {
            'business_date': '2026-06-13',
            'workshop': '园区剪切',
            'shift': '长白班',
            'output_tons': 9.75,
            'energy_kwh': 1200.0,
            'scrap_tons': 0.12,
            'source_file': str(report),
            'source_type': 'output_skill_excel',
        }
    ]


def test_parse_output_skill_xls_file_normalizes_common_columns(tmp_path) -> None:
    xlwt = pytest.importorskip('xlwt')

    report = tmp_path / 'mapping.xls'
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('日报')
    headers = ['日期', '车间', '班次', '产量(吨)', '能耗(kWh)', '废料(吨)']
    values = ['2026-06-13', '热轧', '大夜班', 21.5, 2600, 0.4]
    for index, header in enumerate(headers):
        sheet.write(0, index, header)
    for index, value in enumerate(values):
        sheet.write(1, index, value)
    workbook.save(str(report))

    result = parse_output_skill_reference_file(report)

    assert result['status'] == 'parsed'
    assert result['source_type'] == 'output_skill_excel'
    assert result['rows'] == [
        {
            'business_date': '2026-06-13',
            'workshop': '热轧',
            'shift': '大夜班',
            'output_tons': 21.5,
            'energy_kwh': 2600.0,
            'scrap_tons': 0.4,
            'source_file': str(report),
            'source_type': 'output_skill_excel',
        }
    ]


def test_build_system_mapping_rows_flattens_mes_process_records() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[MesWorkshopProcessRecord.__table__])

    with Session(engine) as db:
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id='mes-1',
                    source_path='ProcessRecord',
                    business_date=date(2026, 6, 13),
                    workshop_name='精整',
                    process_name='包装',
                    device_name='PC-01',
                    batch_no='26A04967',
                    output_weight_tons=12.5,
                    input_weight_tons=13.0,
                    yield_rate=96.15,
                ),
                MesWorkshopProcessRecord(
                    source_id='mes-2',
                    source_path='ProcessRecord',
                    business_date=date(2026, 6, 13),
                    workshop_name='精整',
                    process_name='包装',
                    device_name='PC-01',
                    batch_no='26A04968',
                    output_weight_kg=5000,
                    input_weight_kg=5200,
                ),
                MesWorkshopProcessRecord(
                    source_id='mes-other-date',
                    source_path='ProcessRecord',
                    business_date=date(2026, 6, 14),
                    workshop_name='精整',
                    process_name='包装',
                    device_name='PC-01',
                    output_weight_tons=99,
                ),
            ]
        )
        db.commit()

        rows = build_system_mapping_rows(db, business_date=date(2026, 6, 13))

    assert rows == [
        {
            'business_date': '2026-06-13',
            'workshop': '精整',
            'shift': '',
            'process': '包装',
            'machine': 'PC-01',
            'coil_no': '26A04967',
            'input_tons': 13.0,
            'output_tons': 12.5,
            'yield_rate': 96.15,
            'source_table': 'mes_workshop_process_records',
        },
        {
            'business_date': '2026-06-13',
            'workshop': '精整',
            'shift': '',
            'process': '包装',
            'machine': 'PC-01',
            'coil_no': '26A04968',
            'input_tons': 5.2,
            'output_tons': 5.0,
            'yield_rate': None,
            'source_table': 'mes_workshop_process_records',
        },
    ]
