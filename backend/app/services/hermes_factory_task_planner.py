from __future__ import annotations

from app.services.hermes_factory_brain_types import FactoryBrainNormalizedRequest, FactoryBrainToolPlanStep


def plan_factory_task(normalized: FactoryBrainNormalizedRequest) -> list[FactoryBrainToolPlanStep]:
    steps = [
        FactoryBrainToolPlanStep('dingtalk_context_ingestion', '读取授权钉钉责任人文本和文件', 10, False),
        FactoryBrainToolPlanStep('mes_read', '读取 MES 原始明细，保持只读', 20, True),
        FactoryBrainToolPlanStep('wms_read', '读取 WMS 仓储明细做校验', 30, False),
        FactoryBrainToolPlanStep('datahub_query', '读取数据中枢归一化结果', 40, False),
        FactoryBrainToolPlanStep('historical_report_lookup', '读取历史日报成品对齐口径', 50, False),
        FactoryBrainToolPlanStep('rag_retriever', '检索鑫泰口径、数据路由和行业知识', 60, False),
    ]
    if normalized.output_mode in {'analysis', 'formal_report'}:
        steps.append(FactoryBrainToolPlanStep('factory_analysis', '分析波动、缺口、异常和建议', 70, False))
    if normalized.needs_artifact:
        steps.append(FactoryBrainToolPlanStep('artifact_engine', '生成表格、文档、图表或图片请求', 80, True))
    return sorted(steps, key=lambda item: item.priority)
