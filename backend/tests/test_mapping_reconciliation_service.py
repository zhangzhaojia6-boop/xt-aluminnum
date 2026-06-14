from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from app.services.mapping_reconciliation_service import (
    MappingFieldSpec,
    compare_mapping_rows,
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
