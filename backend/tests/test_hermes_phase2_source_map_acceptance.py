from __future__ import annotations

from app.services.hermes_factory_brain_harness import evaluate_factory_brain_response


def test_source_backed_production_answer_requires_source_map_tool() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle 和 Hermes 事实来源地图。trace_id：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok', 'facts': {'metric_key': 'total_output_daily'}},
        ],
    )

    assert result.passed is True
    assert result.missing == []


def test_source_backed_answer_fails_without_trace_id() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'trace_id' in result.missing