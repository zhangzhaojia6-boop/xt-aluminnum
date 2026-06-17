from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentChannelBinding, AgentProfile, CommunicationChannel
from app.services import agent_communication_service


ZZJ_DEBUG_GROUP_TARGET_KEY = 'zzj-debug-agent-group'

ZZJ_CUSTOM_ROBOT_SPECS = [
    {
        'agent_code': 'factory_dispatch_zzj',
        'channel_key': 'DINGTALK_ROBOT_FACTORY_DISPATCH_WEBHOOK',
        'secret_ref': 'DINGTALK_ROBOT_FACTORY_DISPATCH_SECRET',
        'name': '鑫泰全厂调度 Agent 机器人',
        'min_severity': 'info',
    },
    {
        'agent_code': 'fill_gap_guard_zzj',
        'channel_key': 'DINGTALK_ROBOT_FILL_GAP_WEBHOOK',
        'secret_ref': 'DINGTALK_ROBOT_FILL_GAP_SECRET',
        'name': '鑫泰填报对账 Agent 机器人',
        'min_severity': 'warning',
    },
    {
        'agent_code': 'energy_guard_zzj',
        'channel_key': 'DINGTALK_ROBOT_ENERGY_GUARD_WEBHOOK',
        'secret_ref': 'DINGTALK_ROBOT_ENERGY_GUARD_SECRET',
        'name': '鑫泰能耗守卫 Agent 机器人',
        'min_severity': 'warning',
    },
    {
        'agent_code': 'quality_guard_zzj',
        'channel_key': 'DINGTALK_ROBOT_QUALITY_GUARD_WEBHOOK',
        'secret_ref': 'DINGTALK_ROBOT_QUALITY_GUARD_SECRET',
        'name': '鑫泰质量异常 Agent 机器人',
        'min_severity': 'warning',
    },
    {
        'agent_code': 'daily_report_secretary_zzj',
        'channel_key': 'DINGTALK_ROBOT_DAILY_REPORT_WEBHOOK',
        'secret_ref': 'DINGTALK_ROBOT_DAILY_REPORT_SECRET',
        'name': '鑫泰日报秘书 Agent 机器人',
        'min_severity': 'info',
    },
    {
        'agent_code': 'governance_auditor_zzj',
        'channel_key': 'DINGTALK_ROBOT_GOVERNANCE_AUDITOR_WEBHOOK',
        'secret_ref': 'DINGTALK_ROBOT_GOVERNANCE_AUDITOR_SECRET',
        'name': '鑫泰治理留档 Agent 机器人',
        'min_severity': 'info',
    },
]


@dataclass(frozen=True, slots=True)
class CustomRobotBootstrapOutcome:
    applied: bool
    channel_total: int
    binding_total: int
    channel_keys: list[str]
    notes: list[str]


def build_zzj_custom_robot_plan(*, dry_run: bool = True) -> dict:
    return {
        'target_group': {
            'name': '张兆嘉调试总群',
            'target_key': ZZJ_DEBUG_GROUP_TARGET_KEY,
        },
        'channels': [
            {
                'agent_code': item['agent_code'],
                'channel_type': 'dingtalk_custom_robot',
                'channel_key': item['channel_key'],
                'secret_ref': item['secret_ref'],
                'name': item['name'],
                'target_type': 'debug_group',
                'target_key': ZZJ_DEBUG_GROUP_TARGET_KEY,
                'dry_run': bool(dry_run),
                'min_severity': item['min_severity'],
            }
            for item in ZZJ_CUSTOM_ROBOT_SPECS
        ],
        'safety': {
            'stores_plain_webhook': False,
            'stores_plain_secret': False,
            'default_dry_run': True,
            'outbox_required': True,
            'touches_existing_groups': False,
        },
    }


def ensure_zzj_custom_robot_channels(
    db: Session,
    *,
    apply: bool = False,
    dry_run: bool = True,
) -> CustomRobotBootstrapOutcome:
    plan = build_zzj_custom_robot_plan(dry_run=dry_run)
    channel_keys = [item['channel_key'] for item in plan['channels']]
    notes = [
        '仅配置张兆嘉调试总群的 6 个自定义机器人通道。',
        '数据库只保存环境变量引用名，不保存 webhook 或 secret 明文。',
        f'通道当前 dry_run={bool(dry_run)}；真实发送应只用于已确认的张兆嘉调试总群。',
    ]
    if not apply:
        return CustomRobotBootstrapOutcome(
            applied=False,
            channel_total=len(channel_keys),
            binding_total=len(channel_keys),
            channel_keys=channel_keys,
            notes=notes,
        )

    for spec in plan['channels']:
        agent = _get_agent(db, spec['agent_code'])
        channel = agent_communication_service.register_channel(
            db,
            channel_type=spec['channel_type'],
            channel_key=spec['channel_key'],
            name=spec['name'],
            target_type=spec['target_type'],
            target_key=spec['target_key'],
            dry_run=bool(spec['dry_run']),
            secret_ref=spec['secret_ref'],
            metadata_payload={
                'managed_by': 'ensure_zzj_custom_robot_channels',
                'owner_name': '张兆嘉',
                'webhook_ref': spec['channel_key'],
                'secret_ref': spec['secret_ref'],
                'stores_plain_secret': False,
                'stores_plain_webhook': False,
            },
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code=agent.code,
            channel_key=channel.channel_key,
            channel_type=channel.channel_type,
            min_severity=spec['min_severity'],
        )

    return CustomRobotBootstrapOutcome(
        applied=True,
        channel_total=_count_channels(db, channel_keys),
        binding_total=_count_bindings(db, channel_keys),
        channel_keys=channel_keys,
        notes=notes,
    )


def _get_agent(db: Session, agent_code: str) -> AgentProfile:
    agent = db.query(AgentProfile).filter(AgentProfile.code == agent_code).first()
    if agent is None:
        raise agent_communication_service.AgentCommunicationError(f'agent_not_found:{agent_code}')
    return agent


def _count_channels(db: Session, channel_keys: list[str]) -> int:
    return (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == 'dingtalk_custom_robot',
            CommunicationChannel.channel_key.in_(channel_keys),
        )
        .count()
    )


def _count_bindings(db: Session, channel_keys: list[str]) -> int:
    return (
        db.query(AgentChannelBinding)
        .join(CommunicationChannel, CommunicationChannel.id == AgentChannelBinding.channel_id)
        .filter(
            CommunicationChannel.channel_type == 'dingtalk_custom_robot',
            CommunicationChannel.channel_key.in_(channel_keys),
        )
        .count()
    )
