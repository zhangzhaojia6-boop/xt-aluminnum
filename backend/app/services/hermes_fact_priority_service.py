from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.daily_report_field_contract import (
    SOURCE_LANE_DINGTALK,
    SOURCE_LANE_HISTORICAL_RECORD,
    SOURCE_LANE_OUTPUT_SKILL_REFERENCE,
    SOURCE_LANE_RAG_EXPLANATION_ONLY,
    source_lane_for,
    source_lane_priority,
)

_SOURCE_TYPES = (
    'dingtalk_group_content',
    'dingtalk_specialist',
    'authorized_correction',
    'root_owner',
    'root_owner_correction',
    'mes_wms',
    'mes_wms_readonly',
    'owner_daily',
    'scan_supplement',
    'hub',
    'data_hub',
    'rag',
    'history_report',
    'output_skill',
)
PRIORITY = {
    source_type: source_lane_priority(source_type)
    for source_type in _SOURCE_TYPES
}
_NON_CURRENT_FACT_LANES = {
    SOURCE_LANE_HISTORICAL_RECORD,
    SOURCE_LANE_RAG_EXPLANATION_ONLY,
    SOURCE_LANE_OUTPUT_SKILL_REFERENCE,
}


@dataclass(frozen=True, slots=True)
class FactDecision:
    field_key: str
    value: Any
    source_type: str | None
    source_label: str | None
    status: str
    conflicts: list[dict[str, Any]]
    reason: str
    suggested_action: str | None


def choose_fact_value(field_key: str, candidates: list[dict[str, Any]]) -> FactDecision:
    current_candidates = [
        item
        for item in candidates
        if source_lane_for(str(item.get('source_type') or '')) not in _NON_CURRENT_FACT_LANES
    ]
    if not current_candidates:
        return FactDecision(
            field_key=field_key,
            value=None,
            source_type=None,
            source_label=None,
            status='missing_current_fact',
            conflicts=[],
            reason='RAG、历史日报和输出 skill 不能作为当前事实来源。',
            suggested_action='collect_current_fact',
        )

    selected = max(
        current_candidates,
        key=lambda item: source_lane_priority(str(item.get('source_type') or '')),
    )
    conflicts = [
        {
            'source_type': item.get('source_type'),
            'source_label': item.get('source_label'),
            'value': item.get('value'),
        }
        for item in current_candidates
        if item is not selected and item.get('value') != selected.get('value')
    ]
    source_type = str(selected.get('source_type'))
    suggested_action = (
        'mark_hub_field_for_review'
        if source_lane_for(source_type) == SOURCE_LANE_DINGTALK and conflicts
        else None
    )
    return FactDecision(
        field_key=field_key,
        value=selected.get('value'),
        source_type=source_type,
        source_label=selected.get('source_label'),
        status='selected_with_conflicts' if conflicts else 'selected',
        conflicts=conflicts,
        reason=f'采用 {_source_type_label(source_type)} 来源，按日报事实优先级选择。',
        suggested_action=suggested_action,
    )


def _source_type_label(source_type: str) -> str:
    labels = {
        'dingtalk_group_content': '钉钉群内容',
        'dingtalk_specialist': '钉钉群内容',
        'mes_wms': 'MES/WMS 只读来源',
        'mes_wms_readonly': 'MES/WMS 只读来源',
        'hub': '数据中枢投影',
        'data_hub': '数据中枢投影',
        'owner_daily': '扫码补录',
        'scan_supplement': '扫码补录',
        'authorized_correction': '授权修正',
        'root_owner': '授权修正',
        'root_owner_correction': '授权修正',
    }
    return labels.get(source_type, source_type)
