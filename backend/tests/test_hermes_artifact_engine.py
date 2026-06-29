from datetime import date

from app.services.hermes_artifact_engine import plan_artifacts
from app.services.hermes_factory_brain_types import FactoryBrainDataReference, FactoryBrainIntent
from app.services.hermes_factory_normalization_service import normalize_factory_request


def test_table_artifact_request_for_output_table() -> None:
    intent = FactoryBrainIntent(
        intent_type='artifact_request',
        task_type='artifact_request',
        domain='artifact',
        business_date=date(2026, 6, 26),
    )
    normalized = normalize_factory_request('生成今日产量表格', intent)
    references = [
        FactoryBrainDataReference(
            metric='daily_output',
            value=366.21,
            unit='ton',
            business_date=date(2026, 6, 26),
            source='dingtalk_group_content',
            business_definition='入库成品日合计，含寄存',
            confidence=0.96,
        )
    ]

    artifacts = plan_artifacts(normalized, references)

    assert artifacts[0].artifact_type == 'table'
    assert artifacts[0].format == 'xlsx'
    assert artifacts[0].payload['source_count'] == 1


def test_image_artifact_request_marks_generated_image_as_not_real_photo() -> None:
    intent = FactoryBrainIntent(
        intent_type='artifact_request',
        task_type='artifact_request',
        domain='artifact',
        business_date=date(2026, 6, 26),
    )
    normalized = normalize_factory_request('生成一张工艺流程图片', intent)

    artifacts = plan_artifacts(normalized, [])

    assert artifacts[0].artifact_type == 'image'
    assert artifacts[0].payload['generated_image_is_real_photo'] is False
