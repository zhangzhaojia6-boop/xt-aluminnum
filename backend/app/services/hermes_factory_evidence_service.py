from __future__ import annotations

from app.services.hermes_factory_brain_types import (
    FactoryBrainDataReference,
    FactoryBrainNormalizedRequest,
    FactoryBrainToolPlanStep,
)


def collect_factory_evidence(
    normalized: FactoryBrainNormalizedRequest,
    planned_steps: list[FactoryBrainToolPlanStep],
) -> list[FactoryBrainDataReference]:
    references: list[FactoryBrainDataReference] = []
    if 'daily_output' in normalized.metrics:
        source = 'dingtalk_specialist' if any(
            step.tool == 'dingtalk_context_ingestion' for step in planned_steps
        ) else 'datahub'
        references.append(
            FactoryBrainDataReference(
                metric='daily_output',
                value=None,
                unit='ton',
                business_date=normalized.business_date,
                source=source,
                business_definition='入库成品日合计，含寄存；正式值以责任人文件、MES/WMS 校验为准',
                confidence=0.72,
                metadata={'org_units': normalized.org_units, 'needs_live_query': True},
            )
        )
    if 'monthly_output' in normalized.metrics:
        references.append(
            FactoryBrainDataReference(
                metric='monthly_output',
                value=None,
                unit='ton',
                business_date=normalized.business_date,
                source='historical_report',
                business_definition='按当前业务月累计口径汇总',
                confidence=0.68,
                metadata={'needs_live_query': True},
            )
        )
    return references


def describe_evidence_gap(
    normalized: FactoryBrainNormalizedRequest,
    references: list[FactoryBrainDataReference],
) -> str | None:
    found = {
        reference.metric
        for reference in references
        if reference.value is not None and not reference.metadata.get('needs_live_query')
    }
    missing = [metric for metric in normalized.metrics if metric not in found]
    if not missing:
        return None
    return f"当前缺少 {'、'.join(missing)} 的可追溯数据，建议继续查钉钉责任人文件、MES/WMS 明细或历史日报。"
