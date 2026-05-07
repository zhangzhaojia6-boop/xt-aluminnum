from __future__ import annotations

from datetime import date

import pandas as pd

from app.services.daily_production_canonical_service import (
    daily_production_row_summary_fields,
    parse_daily_production_sheet,
    parse_daily_production_workbook,
)


def _daily_production_frame(rows: list[list]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            ['河南鑫泰铝业生产系统综合日报表               2026年5月3日', None, None, None, None, None, None, None, None, None, None, None],
            ['车间   项目', None, '投料量', None, '日产量', None, '日均', '产生废料', None, '月成品率', '指标', '对比'],
            [None, None, '日合', '累计', '日合', '累计', None, '日合', '累计', None, None, None],
            *rows,
        ]
    )


def test_daily_production_row_summary_fields_are_stable() -> None:
    assert daily_production_row_summary_fields() == [
        'business_date',
        'source_batch_id',
        'sheet_name',
        'source_unit',
        'row_count',
        'daily_input_tons',
        'month_to_date_input_tons',
        'daily_output_tons',
        'month_to_date_output_tons',
        'daily_scrap_tons',
        'month_to_date_scrap_tons',
        'lineage_hash',
        'quality_status',
        'issues',
    ]


def test_parse_daily_production_sheet_extracts_date_rows_and_ton_totals() -> None:
    frame = pd.DataFrame(
        [
            ['河南鑫泰铝业生产系统综合日报表               2026年5月3日', None, None, None, None, None, None, None, None, None, None, None],
            ['车间   项目', None, '投料量', None, '日产量', None, '日均', '产生废料', None, '月成品率', '指标', '对比'],
            [None, None, '日合', '累计', '日合', '累计', None, '日合', '累计', None, None, None],
            ['铸轧', '铸二', 25, 63, 24.18, 61.86, None, 0.82, 1.14, 0.9819, 0.949, 0.0329],
            [None, '铸三', 38, 196, 36.2, 189.21, None, 1.8, 6.79, 0.9653, '/', '/'],
            ['冷轧', '1650', 249.838, 1110.63, 224.54, 1037.31, None, 25.298, 73.32, 0.934, '/', '/'],
        ]
    )

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026)

    assert parsed.status == 'success'
    assert parsed.mapped_data['business_date'] == '2026-05-03'
    assert parsed.mapped_data['source_unit'] == 't'
    assert parsed.mapped_data['row_count'] == 3
    assert parsed.mapped_data['daily_input_tons'] == 312.838
    assert parsed.mapped_data['daily_output_tons'] == 284.92
    assert parsed.mapped_data['month_to_date_output_tons'] == 1288.38
    assert parsed.mapped_data['daily_scrap_tons'] == 27.918
    assert parsed.mapped_data['quality_status'] == 'ready'
    assert parsed.mapped_data['issues'] == []

    rows = parsed.mapped_data['workshop_rows']
    assert rows[0]['workshop_label'] == '铸轧'
    assert rows[1]['workshop_label'] == '铸轧'
    assert rows[1]['project_label'] == '铸三'
    assert rows[2]['workshop_label'] == '冷轧'


def test_parse_daily_production_sheet_flags_suspicious_ten_thousand_scale_output() -> None:
    frame = _daily_production_frame([
        ['冷轧', '2050', 149510, 149510, 120460, 120460, None, 18050, 18050, 0.8057, '/', '/'],
    ])

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026)

    assert parsed.status == 'failed'
    assert parsed.mapped_data['source_unit'] == 't'
    assert parsed.mapped_data['daily_output_tons'] == 120460.0
    assert parsed.mapped_data['quality_status'] == 'blocked'
    assert parsed.mapped_data['issues'] == [
        {
            'code': 'hard_block_kg_as_tons',
            'message': '每日产量日报值 120460.0 超过 50000.0t，疑似把 kg 当作 t，已硬阻断。',
            'row_index': 3,
            'workshop_label': '冷轧',
            'project_label': '2050',
            'value': 120460.0,
        }
    ]


def test_parse_daily_production_sheet_warns_kg_as_tons_above_five_thousand() -> None:
    frame = _daily_production_frame([
        ['冷轧', '2050', 100, 1000, 6000, 80000, None, 0, 0, 0.95, 0.96],
    ])

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026)

    assert parsed.status == 'success'
    assert parsed.mapped_data['quality_status'] == 'warning'
    assert parsed.mapped_data['issues'] == [
        {
            'code': 'suspicious_daily_output_tons',
            'message': '每日产量日报值超过 5000.0t，请核对是否把 kg 当作 t。',
            'row_index': 3,
            'workshop_label': '冷轧',
            'project_label': '2050',
            'value': 6000.0,
        }
    ]


def test_parse_daily_production_sheet_accepts_realistic_daily_values() -> None:
    frame = _daily_production_frame([
        ['铸锭', '', 0, 0, 369, 8000, None, 0, 0, 0, 0],
        ['冷轧', '1650', 100, 3000, 220, 6500, None, 0, 0, 0.95, 0.96],
        ['冷轧', '2050', 80, 2400, 59, 1700, None, 0, 0, 0.95, 0.96],
    ])

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026)

    assert parsed.status == 'success'
    assert parsed.mapped_data['quality_status'] == 'ready'
    assert parsed.mapped_data['issues'] == []


def test_parse_daily_production_sheet_uses_locked_report_date_when_header_is_stale() -> None:
    frame = _daily_production_frame([
        ['冷轧', '2050', 100, 500, 90, 450, None, 10, 50, 0.9, '/', '/'],
    ])

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026, report_date_override=date(2026, 5, 5))

    assert parsed.status == 'success'
    assert parsed.business_date == date(2026, 5, 5)
    assert parsed.mapped_data['business_date'] == '2026-05-05'
    assert parsed.mapped_data['quality_status'] == 'warning'
    assert parsed.mapped_data['issues'] == [
        {
            'code': 'stale_workbook_report_date',
            'message': '每日产量表头日期 2026-05-03 与锁定报告日 2026-05-05 不一致，已按锁定报告日解析。',
            'detected_business_date': '2026-05-03',
            'locked_business_date': '2026-05-05',
        }
    ]


def test_parse_daily_production_sheet_does_not_treat_decimal_metric_as_date() -> None:
    frame = pd.DataFrame(
        [
            ['综合报表', None, None, None, None, None, None, None, None, None, None, None],
            ['车间   项目', None, '投料量', None, '日产量', None, '日均', '产生废料', None, '月成品率', '指标', '对比'],
            [None, None, '日合', '累计', '日合', '累计', None, '日合', '累计', None, None, None],
            ['铸轧', '铸二', 25, 63, 24.18, 61.86, None, 0.82, 1.14, 0.9819, 0.949, 0.0329],
        ]
    )

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026)

    assert parsed.status == 'failed'
    assert parsed.business_date is None
    assert parsed.mapped_data['business_date'] is None
    assert parsed.mapped_data['daily_output_tons'] == 24.18
    assert parsed.mapped_data['quality_status'] == 'blocked'


def test_parse_daily_production_workbook_only_uses_summary_sheet(tmp_path) -> None:
    workbook = tmp_path / '鑫泰每日产量5月.xlsx'
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        pd.DataFrame(
            [
                ['河南鑫泰铝业生产系统综合日报表               2026年5月3日', None, None, None, None, None, None, None, None, None, None, None],
                ['车间   项目', None, '投料量', None, '日产量', None, '日均', '产生废料', None, '月成品率', '指标', '对比'],
                [None, None, '日合', '累计', '日合', '累计', None, '日合', '累计', None, None, None],
                ['冷轧', '2050', 100, 500, 90, 450, None, 10, 50, 0.9, '/', '/'],
            ]
        ).to_excel(writer, sheet_name='综合报表', header=False, index=False)
        pd.DataFrame(
            [
                ['分类报表', None, None, None, None, None],
                [None, None, '老厂', '精整', '拉矫', '2050冷轧'],
                ['铸轧产品', '铝板带', 0, 0, 0, 79.997],
            ]
        ).to_excel(writer, sheet_name='分类报表', header=False, index=False)

    parsed = parse_daily_production_workbook(workbook, year_hint=2026)

    assert [item.sheet_name for item in parsed] == ['综合报表']
    assert parsed[0].mapped_data['daily_output_tons'] == 90.0


def test_parse_daily_production_sheet_stops_before_total_and_energy_sections() -> None:
    frame = pd.DataFrame(
        [
            ['河南鑫泰铝业生产系统综合日报表               2026年5月3日', None, None, None, None, None, None, None, None, None, None, None, None, None],
            ['车间   项目', None, '投料量', None, '日产量', None, '日均', '产生废料', None, '月成品率', '指标', '对比', None, None],
            [None, None, '日合', '累计', '日合', '累计', None, '日合', '累计', None, None, None, None, None],
            ['园区剪切', None, 52.814, 277.341, 49.483, 261.213, None, 3.331, 16.128, 0.9418, '/', '/', 659, 3582],
            ['合计', None, 1985.674, 11325.379, 1935.649, 11258.775, 0, 50.025, 66.604, None, 17.155, None, 94519, 589564],
            ['工业园', None, None, None, None, None, None, None, None, None, None, None, None, None],
            [None, '日产量', '月累计产量', '日道次', '月累计道次', '日电度', None, '月电度', None, None, '日吨电耗', '月吨电耗', '指标', '日燃气'],
            ['铸锭', 314.19, 1678.246, None, None, 7900, None, 38950, None, None, 25.14, 23.2, 30, 25673],
        ]
    )

    parsed = parse_daily_production_sheet('综合报表', frame, year_hint=2026)

    assert parsed.mapped_data['row_count'] == 1
    assert parsed.mapped_data['daily_input_tons'] == 52.814
    assert parsed.mapped_data['daily_output_tons'] == 49.483
    assert parsed.mapped_data['daily_scrap_tons'] == 3.331
