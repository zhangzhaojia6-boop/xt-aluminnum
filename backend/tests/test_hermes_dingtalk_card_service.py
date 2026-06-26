from app.services.hermes_factory_brain_types import FactoryBrainProgress
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


def test_progress_card_uses_auditable_stage_detail_labels() -> None:
    progress = FactoryBrainProgress(
        stage='querying',
        title='Hermes 正在处理：今日产量',
        details=['内部推理: 先猜一个答案再说'],
        trace_id='trace-card-002',
    )

    card = build_progress_card(progress)

    assert '内部推理: 先猜一个答案再说' not in card['details']
    assert '正在查询数据源' in card['details']


def test_progress_card_uses_safe_fallback_for_unknown_stage() -> None:
    progress = FactoryBrainProgress(
        stage='内部推理: 先猜一个答案再说',
        title='Hermes 正在处理：今日产量',
        details=['x'],
        trace_id='trace-card-003',
    )

    card = build_progress_card(progress)

    assert card['stage'] == 'status_updating'
    assert card['details'] == ['状态更新中']
    assert '内部推理: 先猜一个答案再说' not in card['stage']
    assert '内部推理: 先猜一个答案再说' not in card['details']
