from datetime import date

from app.services.hermes_factory_brain_types import (
    FactoryBrainArtifactRequest,
    FactoryBrainCapability,
    FactoryBrainDataReference,
    FactoryBrainIntent,
    FactoryBrainNormalizedRequest,
    FactoryBrainProgress,
    FactoryBrainSkillPackagePlan,
    FactoryBrainToolPlanStep,
)


def test_factory_brain_closed_loop_types_are_serializable_shape() -> None:
    intent = FactoryBrainIntent(
        intent_type='task_instruction',
        task_type='daily_report',
        domain='production',
        business_date=date(2026, 6, 26),
    )
    normalized = FactoryBrainNormalizedRequest(
        intent=intent,
        normalized_text='今日产量',
        business_date=date(2026, 6, 26),
        scope='factory',
        org_units=['factory'],
        metrics=['daily_output', 'monthly_output'],
        data_sources=['dingtalk_group_content', 'mes', 'wms', 'datahub'],
        output_mode='short_answer',
        needs_artifact=False,
    )
    reference = FactoryBrainDataReference(
        metric='daily_output',
        value=366.21,
        unit='ton',
        business_date=date(2026, 6, 26),
        source='dingtalk_group_content',
        business_definition='入库成品日合计，含寄存',
        confidence=0.96,
        metadata={'file_name': '6月26日日报.txt'},
    )
    progress = FactoryBrainProgress(
        stage='validating',
        title='Hermes 正在处理：今日产量',
        details=['已识别：生产日报 / 今日 / 全厂'],
        trace_id='trace-001',
    )
    step = FactoryBrainToolPlanStep(
        tool='mes_read',
        purpose='读取生产明细',
        priority=20,
        required=True,
    )
    artifact = FactoryBrainArtifactRequest(
        artifact_type='table',
        title='今日产量明细',
        format='xlsx',
        payload={'metrics': ['daily_output']},
    )
    skill_plan = FactoryBrainSkillPackagePlan(
        skill_name='factory-normalization',
        reason='统一车间和指标口径',
        files=['SKILL.md'],
        references=['references/metric_definitions.md'],
        tests=['tests/test_normalization_cases.py'],
    )
    capability = FactoryBrainCapability(
        name='browse-research',
        capability_type='browse',
        priority=70,
        enabled=True,
        use_when='API 和文件解析无法拿到页面资料时使用',
    )

    assert normalized.intent.task_type == 'daily_report'
    assert reference.metadata['file_name'] == '6月26日日报.txt'
    assert progress.stage == 'validating'
    assert step.required is True
    assert artifact.format == 'xlsx'
    assert skill_plan.files == ['SKILL.md']
    assert capability.capability_type == 'browse'
