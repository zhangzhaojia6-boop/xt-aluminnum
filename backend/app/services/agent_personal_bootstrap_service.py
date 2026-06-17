from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentChannelBinding, AgentProfile, CommunicationChannel
from app.services import agent_communication_service


ZHANG_ZHAOJIA_DINGTALK_USER_ID = '666327013924069283'
ZHANG_ZHAOJIA_CHANNEL_KEY = ZHANG_ZHAOJIA_DINGTALK_USER_ID

ZHANG_ZHAOJIA_AGENT_SPECS = [
    {
        'code': 'factory_dispatch_zzj',
        'name': '张兆嘉全厂调度 Agent',
        'agent_type': 'reporting',
        'capabilities': ['factory_overview', 'daily_output', 'mes_sync_status', 'major_alerts'],
    },
    {
        'code': 'fill_gap_guard_zzj',
        'name': '张兆嘉填报对账 Agent',
        'agent_type': 'reconciliation',
        'capabilities': ['mes_fill_gaps', 'unmapped_batches', 'weight_mismatch', 'missing_local_entry'],
    },
    {
        'code': 'energy_guard_zzj',
        'name': '张兆嘉能耗守卫 Agent',
        'agent_type': 'energy',
        'capabilities': ['energy_summary', 'energy_per_ton', 'machine_energy_missing'],
    },
    {
        'code': 'quality_guard_zzj',
        'name': '张兆嘉质量异常 Agent',
        'agent_type': 'quality',
        'capabilities': ['quality_issues', 'reconciliation_items', 'alert_timeline'],
    },
    {
        'code': 'daily_report_secretary_zzj',
        'name': '张兆嘉日报秘书 Agent',
        'agent_type': 'reporting',
        'capabilities': ['daily_report_preview', 'report_publish_approval_required'],
    },
    {
        'code': 'governance_auditor_zzj',
        'name': '张兆嘉治理留档 Agent',
        'agent_type': 'governance',
        'capabilities': ['outbox_audit', 'external_message_logs', 'operation_approvals'],
    },
]


@dataclass(frozen=True, slots=True)
class PersonalAgentBootstrapOutcome:
    applied: bool
    dingtalk_user_id: str
    channel_key: str
    agent_codes: list[str]
    channel_dry_run: bool
    agent_total: int
    binding_total: int
    notes: list[str]


def build_zhang_zhaojia_personal_agent_plan(
    *,
    dingtalk_user_id: str = ZHANG_ZHAOJIA_DINGTALK_USER_ID,
    channel_key: str = ZHANG_ZHAOJIA_CHANNEL_KEY,
) -> dict:
    user_id = _clean(dingtalk_user_id) or ZHANG_ZHAOJIA_DINGTALK_USER_ID
    safe_channel_key = _clean(channel_key) or ZHANG_ZHAOJIA_CHANNEL_KEY
    return {
        'target_user': {
            'name': '张兆嘉',
            'dingtalk_user_id': user_id,
        },
        'channel': {
            'channel_type': 'dingtalk_work_notice',
            'channel_key': safe_channel_key,
            'name': '张兆嘉个人钉钉演练通道',
            'target_type': 'user',
            'target_key': user_id,
            'dry_run': True,
        },
        'agents': [
            {
                'code': item['code'],
                'name': item['name'],
                'agent_type': item['agent_type'],
                'scope_type': 'user',
                'target_user_id': user_id,
                'capabilities': list(item['capabilities']),
            }
            for item in ZHANG_ZHAOJIA_AGENT_SPECS
        ],
        'safety': {
            'real_send_enabled': False,
            'touches_existing_groups': False,
            'requires_manual_dingtalk_robot': False,
            'requires_group_open_conversation_id_for_group_delivery': True,
            'outbox_required': True,
            'operation_approval_required_for_writes': True,
        },
    }


def ensure_zhang_zhaojia_personal_agents(
    db: Session,
    *,
    apply: bool = False,
    dingtalk_user_id: str = ZHANG_ZHAOJIA_DINGTALK_USER_ID,
    channel_key: str = ZHANG_ZHAOJIA_CHANNEL_KEY,
) -> PersonalAgentBootstrapOutcome:
    plan = build_zhang_zhaojia_personal_agent_plan(
        dingtalk_user_id=dingtalk_user_id,
        channel_key=channel_key,
    )
    agent_codes = [item['code'] for item in plan['agents']]
    notes = [
        '仅配置张兆嘉个人范围，不绑定管理层群或车间群。',
        '通道保持 dry_run=True；不会真实发送钉钉消息。',
        '后续真实发送可先使用钉钉工作通知仅发给张兆嘉；若改为调试群，需要提供群 openConversationId/chatid 并单独建群通道。',
    ]
    if not apply:
        return PersonalAgentBootstrapOutcome(
            applied=False,
            dingtalk_user_id=plan['target_user']['dingtalk_user_id'],
            channel_key=plan['channel']['channel_key'],
            agent_codes=agent_codes,
            channel_dry_run=True,
            agent_total=len(agent_codes),
            binding_total=len(agent_codes),
            notes=notes,
        )

    channel = agent_communication_service.register_channel(
        db,
        channel_type=plan['channel']['channel_type'],
        channel_key=plan['channel']['channel_key'],
        name=plan['channel']['name'],
        target_type=plan['channel']['target_type'],
        target_key=plan['channel']['target_key'],
        dry_run=True,
        metadata_payload={
            'owner_name': '张兆嘉',
            'owner_dingtalk_user_id': plan['target_user']['dingtalk_user_id'],
            'managed_by': 'ensure_zhang_zhaojia_personal_agents',
            'real_send_enabled': False,
        },
    )
    for spec in plan['agents']:
        agent_communication_service.register_agent(
            db,
            code=spec['code'],
            name=spec['name'],
            agent_type=spec['agent_type'],
            scope_type='user',
            config_payload={
                'owner_name': '张兆嘉',
                'owner_dingtalk_user_id': plan['target_user']['dingtalk_user_id'],
                'capabilities': spec['capabilities'],
                'requires_outbox': True,
                'write_operations_require_approval': True,
            },
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code=spec['code'],
            channel_key=channel.channel_key,
            channel_type=channel.channel_type,
            min_severity='info',
        )

    return PersonalAgentBootstrapOutcome(
        applied=True,
        dingtalk_user_id=plan['target_user']['dingtalk_user_id'],
        channel_key=channel.channel_key,
        agent_codes=agent_codes,
        channel_dry_run=True,
        agent_total=_count_personal_agents(db, agent_codes),
        binding_total=_count_bindings(db, agent_codes, channel.channel_key),
        notes=notes,
    )


def _count_personal_agents(db: Session, agent_codes: list[str]) -> int:
    return (
        db.query(AgentProfile)
        .filter(AgentProfile.code.in_(agent_codes))
        .count()
    )


def _count_bindings(db: Session, agent_codes: list[str], channel_key: str) -> int:
    return (
        db.query(AgentChannelBinding)
        .join(AgentProfile, AgentProfile.id == AgentChannelBinding.agent_profile_id)
        .join(CommunicationChannel, CommunicationChannel.id == AgentChannelBinding.channel_id)
        .filter(
            AgentProfile.code.in_(agent_codes),
            CommunicationChannel.channel_key == channel_key,
        )
        .count()
    )


def _clean(value: str | None) -> str:
    return str(value or '').strip()
