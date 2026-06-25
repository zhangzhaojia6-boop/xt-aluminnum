from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PRIORITY = {
    'root_owner': 1,
    'dingtalk_specialist': 2,
    'hub': 3,
    'mes_wms': 4,
    'rag': 99,
    'history_report': 99,
    'output_skill': 99,
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
        if item.get('source_type') not in {'rag', 'history_report', 'output_skill'}
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

    selected = min(current_candidates, key=lambda item: PRIORITY.get(str(item.get('source_type')), 50))
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
    suggested_action = 'mark_hub_field_for_review' if source_type == 'dingtalk_specialist' and conflicts else None
    return FactDecision(
        field_key=field_key,
        value=selected.get('value'),
        source_type=source_type,
        source_label=selected.get('source_label'),
        status='selected_with_conflicts' if conflicts else 'selected',
        conflicts=conflicts,
        reason=f'采用 {source_type} 来源，按日报事实优先级选择。',
        suggested_action=suggested_action,
    )
