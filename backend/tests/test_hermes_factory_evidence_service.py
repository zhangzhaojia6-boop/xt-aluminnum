from datetime import date

from app.services.hermes_factory_brain_types import FactoryBrainIntent
from app.services.hermes_factory_evidence_service import collect_factory_evidence, describe_evidence_gap
from app.services.hermes_factory_normalization_service import normalize_factory_request
from app.services.hermes_factory_task_planner import plan_factory_task


def test_collects_traceable_data_reference_for_daily_output() -> None:
    intent = FactoryBrainIntent(
        intent_type='task_instruction',
        task_type='daily_output',
        domain='production',
        business_date=date(2026, 6, 26),
    )
    normalized = normalize_factory_request('今日产量', intent)
    references = collect_factory_evidence(normalized, plan_factory_task(normalized))

    assert references
    first = references[0]
    assert first.metric == 'daily_output'
    assert first.unit == 'ton'
    assert first.source in {'dingtalk_specialist', 'mes', 'datahub'}
    assert 0.0 <= first.confidence <= 1.0


def test_gap_message_names_missing_metric_without_hallucinating() -> None:
    intent = FactoryBrainIntent(
        intent_type='task_instruction',
        task_type='energy_analysis',
        domain='energy',
        business_date=date(2026, 6, 26),
    )
    normalized = normalize_factory_request('彩涂能耗是不是异常', intent)

    gap = describe_evidence_gap(normalized, [])

    assert gap == '当前缺少 electricity、gas、unit_consumption 的可追溯数据，建议继续查钉钉责任人文件、MES/WMS 明细或历史日报。'
