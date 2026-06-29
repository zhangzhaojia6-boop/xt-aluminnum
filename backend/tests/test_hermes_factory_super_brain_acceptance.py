from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


def test_day1_acceptance_for_common_natural_language_questions() -> None:
    graph = build_factory_brain_graph(checkpointer=None)
    questions = ['产量', '今天怎么样', '昨日日报', '本月经营情况', '生成今日产量表格']

    for index, question in enumerate(questions):
        result = graph.invoke(
            initial_factory_brain_state(
                trace_id=f'trace-acceptance-{index}',
                text=question,
                actor_user_id=1,
                channel='dingtalk',
            )
        )
        assert result['status'] == 'replied'
        assert result['progress_cards'][-1]['stage'] == 'feedback'
        assert result['normalized_request']['data_sources'][:4] == ['dingtalk_group_content', 'mes', 'wms', 'datahub']
        assert '鑫泰铝业智能大脑' in result['response_text']
        assert '工厂大脑链路' not in result['response_text']
        assert 'Codex token refresh failed' not in result['response_text']
