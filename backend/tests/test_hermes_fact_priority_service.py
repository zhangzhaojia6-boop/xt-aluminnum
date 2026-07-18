from app.domain.daily_report_field_contract import source_lane_priority
from app.services.hermes_fact_priority_service import PRIORITY, choose_fact_value


def test_dingtalk_group_content_wins_over_owner_override_and_system_sources() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'mes_wms', 'value': 359.8, 'source_label': 'MES'},
            {'source_type': 'hub', 'value': 361.0, 'source_label': '数据中枢'},
            {'source_type': 'dingtalk_group_content', 'value': 366.0, 'source_label': '每日产量.xlsx'},
            {'source_type': 'root_owner', 'value': 367.0, 'source_label': '张兆嘉确认'},
        ],
    )

    assert result.value == 366.0
    assert result.source_type == 'dingtalk_group_content'
    assert len(result.conflicts) == 3
    assert '采用 钉钉群内容 来源' in result.reason


def test_dingtalk_group_content_wins_over_hub_and_mes_with_visible_conflicts() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'mes_wms', 'value': 359.8, 'source_label': 'MES'},
            {'source_type': 'hub', 'value': 361.0, 'source_label': '数据中枢'},
            {'source_type': 'dingtalk_group_content', 'value': 366.0, 'source_label': '每日产量.xlsx'},
        ],
    )

    assert result.value == 366.0
    assert result.source_type == 'dingtalk_group_content'
    assert [item['value'] for item in result.conflicts] == [359.8, 361.0]
    assert result.suggested_action == 'mark_hub_field_for_review'


def test_rag_is_never_current_fact_source() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'rag', 'value': 366.0, 'source_label': '历史案例'},
        ],
    )

    assert result.value is None
    assert result.status == 'missing_current_fact'


def test_priority_values_come_from_the_canonical_contract() -> None:
    assert PRIORITY == {
        'dingtalk_group_content': source_lane_priority('dingtalk_group_content'),
        'dingtalk_specialist': source_lane_priority('dingtalk_specialist'),
        'authorized_correction': source_lane_priority('authorized_correction'),
        'root_owner': source_lane_priority('root_owner'),
        'root_owner_correction': source_lane_priority('root_owner_correction'),
        'mes_wms': source_lane_priority('mes_wms'),
        'mes_wms_readonly': source_lane_priority('mes_wms_readonly'),
        'owner_daily': source_lane_priority('owner_daily'),
        'scan_supplement': source_lane_priority('scan_supplement'),
        'hub': source_lane_priority('hub'),
        'data_hub': source_lane_priority('data_hub'),
        'rag': source_lane_priority('rag'),
        'history_report': source_lane_priority('history_report'),
        'output_skill': source_lane_priority('output_skill'),
    }


def test_authorized_correction_wins_over_mes_scan_and_hub() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'hub', 'value': 361.0, 'source_label': '数据中枢'},
            {'source_type': 'owner_daily', 'value': 362.0, 'source_label': '扫码补录'},
            {'source_type': 'mes_wms', 'value': 363.0, 'source_label': 'MES'},
            {'source_type': 'root_owner', 'value': 364.0, 'source_label': '授权修正'},
        ],
    )

    assert result.value == 364.0
    assert result.source_type == 'root_owner'
    assert '授权修正' in result.reason


def test_mes_wms_wins_over_scan_supplement_and_hub() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'hub', 'value': 361.0, 'source_label': '数据中枢'},
            {'source_type': 'owner_daily', 'value': 362.0, 'source_label': '扫码补录'},
            {'source_type': 'mes_wms', 'value': 363.0, 'source_label': 'MES'},
        ],
    )

    assert result.value == 363.0
    assert result.source_type == 'mes_wms'
