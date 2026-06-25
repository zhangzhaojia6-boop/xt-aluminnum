from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


def test_initial_state_records_input_and_trace() -> None:
    state = initial_factory_brain_state(
        trace_id='trace-graph-001',
        text='产量出来了吗',
        actor_user_id=1,
        channel='dingtalk_group',
    )

    assert state['trace_id'] == 'trace-graph-001'
    assert state['input_text'] == '产量出来了吗'
    assert state['state_trace'][0] == 'received'


def test_graph_runs_to_replied_with_stub_nodes() -> None:
    graph = build_factory_brain_graph(checkpointer=None)
    state = initial_factory_brain_state(
        trace_id='trace-graph-002',
        text='产量出来了吗',
        actor_user_id=1,
        channel='dingtalk_group',
    )

    result = graph.invoke(state)

    assert result['status'] == 'replied'
    assert result['state_trace'][-1] == 'reply_to_dingtalk'
    assert 'Hermes 已收到' in result['response_text']
