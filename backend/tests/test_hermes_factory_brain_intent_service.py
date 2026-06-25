from datetime import date

from app.services.hermes_factory_brain_intent_service import classify_factory_brain_intent


def test_classifies_daily_report_task() -> None:
    result = classify_factory_brain_intent('生成 6月19日正式日报', today=date(2026, 6, 25))

    assert result.intent_type == 'task_instruction'
    assert result.task_type == 'daily_report'
    assert result.business_date == date(2026, 6, 19)
    assert result.should_use_factory_brain is True


def test_classifies_anomaly_analysis_task() -> None:
    result = classify_factory_brain_intent('2050 今天电耗为什么高？', today=date(2026, 6, 25))

    assert result.intent_type == 'task_instruction'
    assert result.task_type == 'anomaly_analysis'
    assert result.domain == 'process_quality'
    assert result.entities['workshop'] == '2050'
    assert result.business_date == date(2026, 6, 25)


def test_classifies_business_question() -> None:
    result = classify_factory_brain_intent('今天生产和发货有没有影响合同交付？', today=date(2026, 6, 25))

    assert result.intent_type == 'task_instruction'
    assert result.task_type == 'business_question'
    assert result.domain == 'operations'


def test_classifies_contextual_short_query() -> None:
    result = classify_factory_brain_intent('产量出来了吗', today=date(2026, 6, 25))

    assert result.intent_type == 'contextual_intent'
    assert result.task_type == 'production_readiness'


def test_classifies_rule_management() -> None:
    result = classify_factory_brain_intent('以后日报先看专项责任人发的钉钉文件', today=date(2026, 6, 25))

    assert result.intent_type == 'long_term_rule'
    assert result.task_type == 'rule_management'


def test_falls_back_for_unrelated_text() -> None:
    result = classify_factory_brain_intent('随便聊两句', today=date(2026, 6, 25))

    assert result.intent_type == 'general_chat'
    assert result.should_use_factory_brain is True
