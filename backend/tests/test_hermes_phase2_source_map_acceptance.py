from __future__ import annotations

from app.services.hermes_factory_brain_harness import evaluate_factory_brain_response


def test_source_backed_production_answer_requires_source_map_tool() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle 和 Hermes 事实来源地图。追踪编号：abc',
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


def test_source_backed_answer_fails_when_trace_id_has_no_value() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle。追踪编号:',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'trace_id' in result.missing


def test_source_backed_answer_fails_with_generic_trace_text_without_trace_id() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle。trace: abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'trace_id' in result.missing


def test_source_backed_answer_fails_without_sources_text() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。追踪编号：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'dingtalk_evidence', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'sources' in result.missing


def test_source_backed_answer_fails_when_source_text_only_contains_trace_id() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源： 追踪编号：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'sources' in result.missing


def test_source_backed_answer_fails_when_source_text_only_punctuation() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：-。追踪编号：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'sources' in result.missing


def test_source_backed_answer_fails_when_source_map_missing_or_failed() -> None:
    result_without_source_map = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle。追踪编号：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
        ],
    )

    result_failed_source_map = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle。追踪编号：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'failed'},
        ],
    )

    assert result_without_source_map.passed is False
    assert 'source_map' in result_without_source_map.missing
    assert result_failed_source_map.passed is False
    assert 'source_map' in result_failed_source_map.missing
