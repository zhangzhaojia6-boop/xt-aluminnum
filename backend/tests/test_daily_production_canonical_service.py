from __future__ import annotations

from datetime import date

import pandas as pd

from app.services.daily_production_canonical_service import (
    daily_production_lineage_is_valid,
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


def test_parse_daily_production_workbook_prefers_locked_date_sheet_over_generic_mirror(tmp_path) -> None:
    workbook = tmp_path / 'daily-with-mirror.xlsx'
    dated_mirror = pd.DataFrame(
        [
            ['河南鑫泰铝业生产系统综合日报表               2026年7月17日', None, None, None, None, None],
            ['车间   项目', None, '投料量', None, '日产量', None],
            [None, None, '日合', '累计', '日合', '累计'],
            ['热轧', None, 110, 500, 99, 450],
        ]
    )
    named_summary = dated_mirror.copy()
    named_summary.iat[3, 4] = 90
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        dated_mirror.to_excel(writer, sheet_name='2026-7-17', header=False, index=False)
        named_summary.to_excel(writer, sheet_name='综合报表', header=False, index=False)

    parsed = parse_daily_production_workbook(
        workbook,
        year_hint=2026,
        report_date_override=date(2026, 7, 17),
    )

    assert [item.sheet_name for item in parsed] == ['2026-7-17']
    assert parsed[0].mapped_data['daily_output_tons'] == 99.0
    assert {
        'code': 'ignored_duplicate_summary_sheet',
        'selected_sheet': '2026-7-17',
        'ignored_sheets': ['综合报表'],
    } in parsed[0].mapped_data['issues']


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


def test_parse_workbook_extracts_auditable_report_metrics_from_summary_and_outsourcing(tmp_path) -> None:
    report_date = date(2026, 7, 17)
    summary = pd.DataFrame('', index=range(61), columns=range(34))
    summary.iat[0, 0] = '河南鑫泰铝业生产系统综合日报表               2026年7月17日'
    summary.iloc[1, :12] = ['车间   项目', '', '投料量', '', '日产量', '', '日均', '产生废料', '', '月成品率', '指标', '对比']
    summary.iloc[2, :12] = ['', '', '日合', '累计', '日合', '累计', '', '日合', '累计', '', '', '']
    summary.iloc[3, :12] = ['铸锭', '', 313.55, 5009.364, 309.806, 4788.837, '', '', 220.527, 0.956, 0.978, -0.022]
    summary.iat[39, 0] = '合计'
    summary.iat[1, 26] = '产量'
    summary.iat[2, 26] = '日合计'
    summary.iat[2, 27] = '月累计'
    summary.iat[39, 26] = 285.545
    summary.iat[39, 27] = 5185.177
    summary.iloc[47, :18] = [
        '', '日产量', '月累计产量', '日道次', '月累计道次', '日电度', '', '月电度', '', '',
        '日吨电耗', '月吨电耗', '指标', '日燃气', '月燃气', '日吨燃气', '月吨燃气', '指标',
    ]
    summary.iloc[48, :18] = [
        '铸轧分厂', 80.52, 1607.09, '', '', 6771, '', 130222, '', '', 84.0909, 81.0297, '',
        11055, 192117, 137.2951, 119.5434, '',
    ]
    summary.iloc[49, :18] = [
        '铸锭', 309.806, 4788.837, '', '', 8850, '', 148000, '', '', 28.5663, 30.9052, 30,
        24524, 451382, 79.1592, 94.2571, 75,
    ]
    summary.iloc[50, :18] = [
        '热轧', 346.32, 4250.62, '', '', 44480, '', 580160, '', '', 128.4361, 136.4883, 170,
        9922, 126466, 28.6498, 29.7524, 31,
    ]
    summary.iloc[51, :13] = ['1650', 90.43, 2486.133, 34, 894, 10030, '', 249196, '', '', 110.9145, 100.2344, '']
    summary.iloc[58, :18] = ['彩涂', 0, 0, '', '', 0, '', 0, '', '', 0, 0, 80, 0, 0, 0, 0, 50]
    summary.iloc[59, :5] = ['轧机', 188.09, 5352.493, 125, 2698]

    outsourced = pd.DataFrame('', index=range(8), columns=range(33))
    outsourced.iat[0, 1] = '外加工'
    outsourced.iat[1, 0] = '车间'
    for day in range(1, 32):
        outsourced.iat[1, day] = date(2026, 7, day)
    outsourced.iat[2, 0] = '拉矫铸轧'
    outsourced.iat[2, 15] = 6.189
    outsourced.iat[2, 16] = 5.164
    outsourced.iat[2, 17] = 13.068
    outsourced.iat[5, 0] = '园区剪切'
    outsourced.iat[5, 15] = 19.334
    outsourced.iat[5, 16] = 70.554
    outsourced.iat[5, 17] = 25.823
    outsourced.iat[6, 0] = '合计：'

    workbook = tmp_path / 'daily-production.xlsx'
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        summary.to_excel(writer, sheet_name='综合报表', header=False, index=False)
        outsourced.to_excel(writer, sheet_name='外加工', header=False, index=False)

    parsed = parse_daily_production_workbook(
        workbook,
        year_hint=2026,
        report_date_override=report_date,
    )
    metrics = {item['field_name']: item for item in parsed[0].mapped_data['report_metrics']}

    assert daily_production_lineage_is_valid(parsed[0].mapped_data) is True
    assert metrics['total_output_daily']['value'] == 285.545
    assert metrics['total_output_month']['value'] == 5185.177
    assert metrics['cost_basis_weight']['value'] == 285.545
    assert metrics['cast_roll_month']['value'] == 1607.09
    assert metrics['cold_1650_pass_daily']['value'] == 34
    assert metrics['cold_1650_pass_month']['value'] == 894
    assert metrics['foundry_gas_per_ton_daily']['value'] == 79.1592
    assert metrics['hot_roll_gas_per_ton_month']['value'] == 29.7524
    assert metrics['coating_daily']['value'] == 0
    assert metrics['coating_gas_per_ton_month']['value'] == 0
    assert metrics['outsourced_daily']['value'] == 38.891
    assert metrics['outsourced_month']['value'] == 140.132
    assert metrics['outsourced_daily']['source_anchors'] == [
        {'sheet_name': '外加工', 'row_index': 2, 'column_index': 17},
        {'sheet_name': '外加工', 'row_index': 5, 'column_index': 17},
    ]

    inferred = parse_daily_production_workbook(workbook, year_hint=2026)
    inferred_metrics = {item['field_name']: item for item in inferred[0].mapped_data['report_metrics']}
    assert inferred[0].mapped_data['business_date'] == report_date.isoformat()
    assert inferred_metrics['outsourced_daily']['value'] == 38.891
    assert inferred_metrics['outsourced_month']['value'] == 140.132
