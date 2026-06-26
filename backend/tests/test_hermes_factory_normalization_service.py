from datetime import date

from app.services.hermes_factory_brain_types import FactoryBrainIntent
from app.services.hermes_factory_normalization_service import normalize_factory_request


def test_normalizes_workshop_metric_sources_and_output_mode() -> None:
    intent = FactoryBrainIntent(
        intent_type='task_instruction',
        task_type='daily_output',
        domain='production',
        business_date=date(2026, 6, 26),
        entities={'workshop': '1650冷轧'},
    )

    result = normalize_factory_request('1650今天产量发我', intent)

    assert result.normalized_text == '1650今天产量发我'
    assert result.scope == 'workshop'
    assert result.org_units == ['1650']
    assert result.metrics == ['daily_output', 'monthly_output']
    assert result.data_sources[:4] == ['dingtalk_specialist', 'mes', 'wms', 'datahub']
    assert result.output_mode == 'short_answer'


def test_normalizes_artifact_request() -> None:
    intent = FactoryBrainIntent(
        intent_type='artifact_request',
        task_type='artifact_request',
        domain='artifact',
        business_date=date(2026, 6, 26),
    )

    result = normalize_factory_request('生成一张今日产量表格', intent)

    assert result.needs_artifact is True
    assert result.output_mode == 'artifact'
    assert 'daily_output' in result.metrics
