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
    assert result.task_type == 'general_chat'
    assert result.should_use_factory_brain is False


def test_common_business_phrases_route_before_model_fallback() -> None:
    today = date(2026, 6, 26)

    cases = [
        ('产量', 'production', 'daily_output'),
        ('今天怎么样', 'operations', 'factory_overview'),
        ('昨日日报', 'production', 'daily_report'),
        ('本月经营情况', 'operations', 'monthly_operation'),
        ('年度经营情况', 'operations', 'yearly_operation'),
        ('1650今天是不是低了', 'production', 'anomaly_analysis'),
        ('库存够不够', 'inventory', 'inventory_query'),
        ('合同余量', 'contract', 'contract_balance'),
        ('能耗是不是异常', 'energy', 'energy_analysis'),
        ('成本核算发我', 'cost', 'cost_analysis'),
        ('生成一张产量表格', 'artifact', 'artifact_request'),
    ]

    for text, domain, task_type in cases:
        intent = classify_factory_brain_intent(text, today=today)
        assert intent.should_use_factory_brain is True
        assert intent.domain == domain
        assert intent.task_type == task_type


def test_non_business_question_uses_general_answer_lane() -> None:
    intent = classify_factory_brain_intent('给我讲个轻松的笑话', today=date(2026, 6, 26))

    assert intent.should_use_factory_brain is False
    assert intent.domain == 'general'
    assert intent.task_type == 'general_chat'


def test_general_non_business_natural_language_does_not_use_factory_brain() -> None:
    today = date(2026, 6, 26)

    for text in ('你好', '随便聊两句', '帮我随便说点什么'):
        intent = classify_factory_brain_intent(text, today=today)
        assert intent.intent_type == 'general_chat'
        assert intent.domain == 'general'
        assert intent.task_type == 'general_chat'
        assert intent.should_use_factory_brain is False


def test_classifies_yield_feedback_and_meta_skill_intents() -> None:
    today = date(2026, 6, 26)

    cases = [
        ('成品率怎么样', 'quality', 'yield_analysis'),
        ('成材率分析一下', 'quality', 'yield_analysis'),
        ('收得率是不是低了', 'quality', 'yield_analysis'),
        ('我要反馈一个问题', 'feedback', 'feedback_learning'),
        ('你说错了，重新学一下', 'feedback', 'feedback_learning'),
        ('这个数据我想纠错', 'feedback', 'feedback_learning'),
        ('我有点意见', 'feedback', 'feedback_learning'),
        ('帮我生成 skill', 'skill_factory', 'meta_skill_request'),
        ('我想做一个技能包', 'skill_factory', 'meta_skill_request'),
        ('给我一个 agent 方案', 'skill_factory', 'meta_skill_request'),
        ('参考 GitHub skill 帮我做', 'skill_factory', 'meta_skill_request'),
    ]

    for text, domain, task_type in cases:
        intent = classify_factory_brain_intent(text, today=today)
        assert intent.should_use_factory_brain is True
        assert intent.domain == domain
        assert intent.task_type == task_type
