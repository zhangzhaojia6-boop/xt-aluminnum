from datetime import date

from app.services.hermes_factory_brain_types import FactoryBrainIntent
from app.services.hermes_factory_normalization_service import normalize_factory_request
from app.services.hermes_factory_task_planner import plan_factory_task


def test_daily_output_plan_uses_dingtalk_mes_wms_datahub_then_history() -> None:
    intent = FactoryBrainIntent(
        intent_type='task_instruction',
        task_type='daily_output',
        domain='production',
        business_date=date(2026, 6, 26),
    )
    normalized = normalize_factory_request('今日产量', intent)

    steps = plan_factory_task(normalized)

    assert [step.tool for step in steps[:5]] == [
        'dingtalk_context_ingestion',
        'mes_read',
        'wms_read',
        'datahub_query',
        'historical_report_lookup',
    ]
    assert steps[0].required is False
    assert steps[1].required is True


def test_artifact_plan_adds_artifact_engine() -> None:
    intent = FactoryBrainIntent(
        intent_type='artifact_request',
        task_type='artifact_request',
        domain='artifact',
        business_date=date(2026, 6, 26),
    )
    normalized = normalize_factory_request('生成今日产量表格', intent)

    steps = plan_factory_task(normalized)

    assert steps[-1].tool == 'artifact_engine'
