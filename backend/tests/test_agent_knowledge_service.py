from __future__ import annotations

from app.services import agent_knowledge_service as knowledge_service


def test_metric_rule_answer_includes_sources() -> None:
    answer = knowledge_service.answer_question('全厂总产量和车间产量分别怎么算？')

    assert answer['can_answer'] is True
    assert answer['confidence'] == 'high'
    assert '最后入库' in answer['answer'] or '包装' in answer['answer']
    assert '车间产量' in answer['answer']
    assert answer['citations']
    assert answer['citations'][0]['source_ref']


def test_mes_and_manual_fill_conflict_uses_mes_as_main_and_manual_as_supplement() -> None:
    answer = knowledge_service.answer_question('MES数据和人工填报数据冲突时以前端哪个为准？')

    assert answer['can_answer'] is True
    assert 'MES' in answer['answer']
    assert '人工填报' in answer['answer']
    assert '补录' in answer['answer'] or '对照' in answer['answer']
    assert answer['citations']


def test_mes_field_question_explains_tracking_card_and_process_fields() -> None:
    answer = knowledge_service.answer_question('随行卡号、客户、合金、规格、当前工艺这些MES字段在系统里有什么用？')

    assert answer['can_answer'] is True
    assert '随行卡' in answer['answer']
    assert '客户' in answer['answer']
    assert '合金' in answer['answer']
    assert '当前工艺' in answer['answer']
    assert answer['citations']


def test_anomaly_question_explains_review_flow_without_auto_write() -> None:
    answer = knowledge_service.answer_question('异常检测发现MES和填报不一致应该怎么处理？')

    assert answer['can_answer'] is True
    assert '待核查' in answer['answer'] or '人工确认' in answer['answer']
    assert '不能直接改' in answer['answer'] or '不能直接进入正式指标' in answer['answer']
    assert answer['citations']


def test_realtime_metric_question_is_blocked_to_avoid_fabrication() -> None:
    answer = knowledge_service.answer_question('今天实时产量是多少？')

    assert answer['can_answer'] is False
    assert answer['confidence'] == 'blocked_realtime'
    assert answer['citations'] == []
    assert '不能提供实时数值' in answer['answer']
    assert '实时接口' in answer['missing_data']


def test_unknown_question_returns_missing_source() -> None:
    answer = knowledge_service.answer_question('宿舍食堂菜单怎么安排？')

    assert answer['can_answer'] is False
    assert answer['confidence'] == 'low'
    assert answer['citations'] == []
    assert '没有找到足够资料' in answer['answer']


def test_grounded_prompt_contains_sources_and_no_realtime_permission() -> None:
    answer = knowledge_service.answer_question('发布日报前需要什么确认？')
    prompt = knowledge_service.build_grounded_prompt('发布日报前需要什么确认？', answer)

    assert '只允许根据这些来源回答' in prompt
    assert '不能编造实时产量' in prompt
    assert 'SOURCE' in prompt
    assert answer['citations'][0]['entry_id'] in prompt


def test_list_knowledge_entries_covers_stage_eight_rule_groups() -> None:
    categories = {item['category'] for item in knowledge_service.list_knowledge_entries()}

    for category in {
        'daily_report_rule',
        'mes_field_rule',
        'workshop_rule',
        'anomaly_rule',
        'fill_rule',
        'permission_rule',
    }:
        assert category in categories
