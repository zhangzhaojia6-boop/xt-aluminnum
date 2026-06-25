from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class FactoryBrainHarnessResult:
    scenario: str
    passed: bool
    score: float
    missing: list[str]


def evaluate_factory_brain_response(
    *,
    scenario: str,
    response_text: str,
    tool_trace: list[dict[str, Any]],
) -> FactoryBrainHarnessResult:
    checks = _checks_for_scenario(scenario)
    missing = [item for item in checks if not _check(item, response_text, tool_trace, scenario=scenario)]
    score = round((len(checks) - len(missing)) / max(1, len(checks)), 4)
    return FactoryBrainHarnessResult(
        scenario=scenario,
        passed=score >= 0.8,
        score=score,
        missing=missing,
    )


def _checks_for_scenario(scenario: str) -> list[str]:
    if scenario == 'daily_report':
        return ['judgment', 'formal_report', 'workshop_detail', 'sources', 'conflicts', 'output_skill_alignment']
    if scenario == 'anomaly_analysis':
        return ['current_fact', 'process_knowledge', 'reason_order', 'suggested_action']
    if scenario == 'business_question':
        return ['production', 'inventory', 'delivery', 'contract']
    if scenario == 'source_backed_answer':
        return ['conclusion', 'sources', 'source_map', 'trace_id']
    return ['response']


def _check(
    name: str,
    response_text: str,
    tool_trace: list[dict[str, Any]],
    *,
    scenario: str,
) -> bool:
    if name == 'conclusion':
        return '结论' in response_text
    if name == 'judgment':
        return '工厂大脑判断单' in response_text
    if name == 'formal_report':
        return '正式日报正文' in response_text
    if name == 'workshop_detail':
        return '各车间明细' in response_text
    if name == 'sources':
        if scenario == 'source_backed_answer':
            match = re.search(r'数据来源[：:]\s*(.*)', response_text)
            if match is None:
                return False
            sources_part = match.group(1)
            sources_before_trace_id = re.split(r'(?=(?:trace_id|trace)[：:])', sources_part, maxsplit=1)[0]
            return bool(sources_before_trace_id.strip())
        return '数据来源' in response_text or any(
            item.get('tool') == 'dingtalk_evidence' for item in tool_trace
        )
    if name == 'conflicts':
        return '冲突' in response_text
    if name == 'output_skill_alignment':
        return any(item.get('tool') == 'output_skill_alignment' and item.get('status') == 'ok' for item in tool_trace)
    if name == 'source_map':
        return any(item.get('tool') == 'source_map' and item.get('status') == 'ok' for item in tool_trace)
    if name == 'trace_id':
        return 'trace_id' in response_text
    if name == 'current_fact':
        return any(item.get('tool') == 'hub_query' and item.get('status') == 'ok' for item in tool_trace)
    if name == 'process_knowledge':
        return any(item.get('tool') == 'rag_route' and 'process' in item.get('knowledge_types', []) for item in tool_trace)
    if name == 'reason_order':
        return '原因排序' in response_text
    if name == 'suggested_action':
        return '建议动作' in response_text
    if name in {'production', 'inventory', 'delivery', 'contract'}:
        return any(name in item.get('facts', []) for item in tool_trace)
    if name == 'response':
        return bool(response_text.strip())
    return False
