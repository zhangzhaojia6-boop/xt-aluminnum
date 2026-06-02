from __future__ import annotations

from typing import Any


COLD_ROLL_FINAL_STAGES = {'finished', 'finished_product', '成品', '成品切边'}
COLD_ROLL_STAGE_LABELS = {
    'billet': '开坯',
    'intermediate_anneal': '中退',
    'finished': '成品',
}


def normalize_process_stage(extra_payload: Any) -> str:
    if not isinstance(extra_payload, dict):
        return ''
    value = extra_payload.get('process_stage')
    if value in (None, ''):
        return ''
    return str(value).strip()


def process_stage_label(stage: str) -> str:
    return COLD_ROLL_STAGE_LABELS.get(stage, stage or '未标记')


def cold_roll_counts_as_workshop_output(extra_payload: Any) -> bool:
    return normalize_process_stage(extra_payload) in COLD_ROLL_FINAL_STAGES


def counts_as_workshop_output(*, workshop_type: str | None, extra_payload: Any) -> bool:
    if str(workshop_type or '').strip() != 'cold_roll':
        return True
    return cold_roll_counts_as_workshop_output(extra_payload)


def pass_count(extra_payload: Any) -> int:
    if not isinstance(extra_payload, dict):
        return 0
    raw = extra_payload.get('pass_count')
    if raw in (None, ''):
        return 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return int(value)
