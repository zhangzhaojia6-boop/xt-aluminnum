from app.services.hermes_factory_brain_harness import evaluate_factory_brain_response


def test_daily_report_acceptance_requires_conflicts_and_sources() -> None:
    result = evaluate_factory_brain_response(
        scenario='daily_report',
        response_text='工厂大脑判断单\n正式日报正文\n各车间明细\n数据来源：数据中枢、钉钉专项文件。\n冲突：总产量。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'dingtalk_evidence', 'status': 'ok'},
            {'tool': 'output_skill_alignment', 'status': 'ok'},
        ],
    )

    assert result.passed is True
    assert result.score >= 0.8


def test_anomaly_acceptance_requires_process_knowledge_and_current_fact() -> None:
    result = evaluate_factory_brain_response(
        scenario='anomaly_analysis',
        response_text='2050 吨电耗偏高。原因排序：产量分母、开机时间、停机说明。建议动作：核对班次。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'rag_route', 'status': 'ok', 'knowledge_types': ['metric', 'process', 'case']},
            {'tool': 'dingtalk_evidence', 'status': 'ok'},
        ],
    )

    assert result.passed is True


def test_business_question_acceptance_requires_contract_and_delivery() -> None:
    result = evaluate_factory_brain_response(
        scenario='business_question',
        response_text='今日生产和发货暂不影响合同交付。已核对生产、库存、发货、合同、余合同。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok', 'facts': ['production', 'inventory', 'delivery', 'contract']},
        ],
    )

    assert result.passed is True
