from app.services.hermes_fact_priority_service import choose_fact_value


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
