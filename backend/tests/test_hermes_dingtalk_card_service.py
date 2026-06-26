from app.services.hermes_dingtalk_card_service import build_progress_card, build_progress_sequence


def test_progress_sequence_uses_single_card_business_id() -> None:
    stages = build_progress_sequence(trace_id='trace-card-001', title='Hermes 正在处理：今日产量')

    assert [stage.stage for stage in stages] == [
        'received',
        'recognized',
        'querying',
        'validating',
        'generating',
        'completed',
        'feedback',
    ]
    assert all(stage.trace_id == 'trace-card-001' for stage in stages)


def test_progress_card_contains_feedback_actions() -> None:
    progress = build_progress_sequence(trace_id='trace-card-001', title='Hermes 正在处理：今日产量')[-1]

    card = build_progress_card(progress)

    assert card['cardBizId'] == 'hermes-factory-brain-trace-card-001'
    assert card['stage'] == 'feedback'
    assert [action['key'] for action in card['actions']] == ['view_sources', 'rerun', 'accept', 'mark_inaccurate']
