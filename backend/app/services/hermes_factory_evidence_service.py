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
        source = 'dingtalk_group_content' if any(
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
    missing_labels = '、'.join(_metric_label(metric) for metric in missing)
    return f"当前缺少 {missing_labels} 的可追溯数据，建议继续查钉钉群文件和聊天内容、MES/WMS 只读明细或历史日报。"


def _metric_label(metric: str) -> str:
    labels = {
        'daily_output': '日产量',
        'monthly_output': '月累计产量',
        'inventory': '库存',
        'contract_balance': '合同余量',
        'yield_rate': '成品率',
        'energy_cost': '能耗成本',
        'anomaly': '异常',
        'monthly_operation': '月度经营',
        'yearly_operation': '年度经营',
        'artifact_request': '成果物请求',
        'daily_report': '日报',
    }
    return labels.get(str(metric or '').strip(), str(metric or '').strip())
