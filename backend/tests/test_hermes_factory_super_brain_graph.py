from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


def test_graph_runs_full_closed_loop_for_output_question() -> None:
    graph = build_factory_brain_graph(checkpointer=None)
    state = initial_factory_brain_state(
        trace_id='trace-super-brain-001',
        text='今日产量',
        actor_user_id=1,
        channel='dingtalk',
    )

    result = graph.invoke(state)

    assert result['status'] == 'replied'
    assert result['intent']['task_type'] == 'daily_output'
    assert result['normalized_request']['metrics'] == ['daily_output', 'monthly_output']
    assert result['tool_plan'][0]['tool'] == 'dingtalk_context_ingestion'
    assert result['data_references'][0]['metric'] == 'daily_output'
    assert result['progress_cards'][-1]['stage'] == 'feedback'
    assert '来源' in result['response_text']
