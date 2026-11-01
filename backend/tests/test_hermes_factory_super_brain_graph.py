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

    assert result['status'] == 'evidence_pending'
    assert result['intent']['task_type'] == 'daily_output'
    assert result['normalized_request']['metrics'] == ['daily_output', 'monthly_output']
    assert result['tool_plan'][0]['tool'] == 'dingtalk_context_ingestion'
    assert result['data_references'][0]['metric'] == 'daily_output'
    assert result['progress_cards'][-1]['stage'] == 'feedback'
    assert '来源' in result['response_text']


def test_graph_does_not_claim_reply_when_no_evidence_value_was_fetched() -> None:
    graph = build_factory_brain_graph(checkpointer=None)
    result = graph.invoke(
        initial_factory_brain_state(
            trace_id='trace-super-brain-unfetched',
            text='今天产量多少？',
            actor_user_id=1,
            channel='dingtalk',
        )
    )

    assert all(reference['value'] is None for reference in result['data_references'])
    assert result['status'] == 'evidence_pending'
    assert '已按现场证据链处理' not in result['response_text']
    assert '暂时还不能确认结果' in result['response_text']


def test_graph_replies_when_an_evidence_value_was_fetched(monkeypatch) -> None:
    from app.services import hermes_langgraph_app

    original = hermes_langgraph_app.collect_factory_evidence

    def fetched(normalized, plan):
        from dataclasses import replace

        references = original(normalized, plan)
        return [replace(references[0], value=1935.649), *references[1:]]

    monkeypatch.setattr(hermes_langgraph_app, 'collect_factory_evidence', fetched)
    graph = build_factory_brain_graph(checkpointer=None)
    result = graph.invoke(
        initial_factory_brain_state(
            trace_id='trace-super-brain-fetched',
            text='今日产量',
            actor_user_id=1,
            channel='dingtalk',
        )
    )

    assert result['status'] == 'replied'
    assert '已按现场证据链处理' in result['response_text']
