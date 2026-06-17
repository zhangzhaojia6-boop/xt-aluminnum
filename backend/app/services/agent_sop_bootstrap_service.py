from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentProfile


ZZJ_AGENT_WORKFLOWS: dict[str, dict[str, Any]] = {
    'factory_dispatch_zzj': {
        'role': '全厂调度 Agent',
        'daily_triggers': ['07:30_initial_report', '09:35_correction_check'],
        'responsibilities': ['factory_overview', 'mes_sync_status', 'major_alerts'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'fill_gap_guard_zzj': {
        'role': '填报对账 Agent',
        'daily_triggers': ['07:30_gap_scan', '09:35_manual_supplement_diff'],
        'responsibilities': ['missing_fields', 'unmatched_machine', 'manual_vs_mes_diff'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'energy_guard_zzj': {
        'role': '能耗守卫 Agent',
        'daily_triggers': ['07:30_energy_snapshot', '09:35_energy_recalc'],
        'responsibilities': ['electricity', 'gas', 'energy_per_ton_by_packaging_output'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'quality_guard_zzj': {
        'role': '质量异常 Agent',
        'daily_triggers': ['07:30_quality_gate', '09:35_quality_recheck'],
        'responsibilities': ['quality_gate', 'open_quality_issues', 'blocking_summary'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
    'daily_report_secretary_zzj': {
        'role': '日报秘书 Agent',
        'initial_report_time': '07:30',
        'correction_report_time': '09:35',
        'daily_triggers': ['07:30_initial_report_send', '09:35_correction_report_send_if_changed'],
        'responsibilities': ['render_factory_report', 'render_workshop_cards', 'queue_outbox'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
        'requires_final_confirmation': True,
    },
    'governance_auditor_zzj': {
        'role': '治理留档 Agent',
        'daily_triggers': ['after_initial_report', 'after_correction_report'],
        'responsibilities': ['outbox_audit', 'external_message_logs', 'version_diff_archive'],
        'requires_outbox': True,
        'can_direct_send_dingtalk': False,
    },
}


@dataclass(frozen=True, slots=True)
class AgentSopBootstrapOutcome:
    applied: bool
    agent_total: int
    workflow_total: int
    agent_codes: list[str]


def build_zzj_agent_sop_plan() -> dict[str, Any]:
    return {
        'agent_codes': list(ZZJ_AGENT_WORKFLOWS),
        'workflows': ZZJ_AGENT_WORKFLOWS,
        'safety': {
            'requires_outbox': True,
            'direct_dingtalk_send_allowed': False,
            'stores_secrets': False,
        },
    }


def ensure_zzj_agent_sop(db: Session, *, apply: bool = False) -> AgentSopBootstrapOutcome:
    codes = list(ZZJ_AGENT_WORKFLOWS)
    agents = db.query(AgentProfile).filter(AgentProfile.code.in_(codes)).all()
    if apply:
        missing_codes = [code for code in codes if code not in {agent.code for agent in agents}]
        if missing_codes:
            raise ValueError(f'missing required AgentProfile rows: {", ".join(missing_codes)}')
        by_code = {agent.code: agent for agent in agents}
        for code, workflow in ZZJ_AGENT_WORKFLOWS.items():
            agent = by_code[code]
            payload = dict(agent.config_payload or {})
            payload['workflow'] = dict(workflow)
            payload['sop_version'] = '2026-06-18'
            agent.config_payload = payload
        db.flush()
    return AgentSopBootstrapOutcome(
        applied=bool(apply),
        agent_total=len(agents),
        workflow_total=len(ZZJ_AGENT_WORKFLOWS),
        agent_codes=codes,
    )
