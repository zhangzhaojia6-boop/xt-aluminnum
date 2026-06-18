from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models.agent_communication import AgentChannelBinding, AgentOutboxMessage, AgentProfile, CommunicationChannel


FACTORY_PROFILE_CODE = 'xt-factory-controller'
FACTORY_PROFILE_NAME = '鑫泰铝业工厂总控'
SAFE_SYSTEM_UNDERSTANDING_FILENAME = 'system-understanding-consolidated-2026-06-14.rag-safe.md'

_SENSITIVE_LINE_PATTERN = re.compile(
    r'(?i)'
    r'(password|passwd|pwd|secret|token|api[_-]?key|app[_-]?secret|authorization|'
    r'access[_-]?token|refresh[_-]?token|webhook|cookie|database[_-]?url|'
    r'connection[_-]?string|client[_-]?secret|数据库密码|密钥|连接串)'
)
_ASSIGNMENT_PATTERN = re.compile(r'[:=：]\s*\S+')
_DINGTALK_WEBHOOK_PATTERN = re.compile(r'https://oapi\.dingtalk\.com/robot/send\?[^\s)>\]]+', re.IGNORECASE)
_PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----',
    re.IGNORECASE | re.DOTALL,
)
_BEARER_PATTERN = re.compile(r'(?i)authorization\s*[:=]\s*bearer\s+\S+')
_CONNECTION_AUTH_PATTERN = re.compile(r'(?i)([a-z][a-z0-9+.-]*://)([^:/@\s]+):([^/@\s]+)@')


@dataclass(frozen=True, slots=True)
class SafeDocumentResult:
    source_path: str
    output_path: str
    redacted_line_count: int
    original_size: int
    safe_size: int


def build_factory_profile_memory() -> str:
    return '\n'.join(
        [
            '# 鑫泰铝业 Hermes 工厂总控记忆',
            '',
            'Hermes 在钉钉鑫泰铝业通道中只作为工厂总控入口。',
            '数字事实只能来自数据中枢 CLI/API、MES 投影表或带来源的 RAG。',
            'RAG 只回答稳定知识、日报口径、MES 路线、SOP 和系统理解，不用于猜测实时产量。',
            '包装产量/总产量优先来自 WMS_InStock.TotalNetWeight + InStockDate。',
            '日报、补产量、正式通知只生成审批预览和 outbox，不绕过审批直接正式发送。',
            '旧 Hermes 个人任务、飞书项目作战室、X 自动化和现金流记忆属于 legacy_archive，不参与工厂群回答。',
            '数据中枢旧 Agent 是后台业务工具和审计留档层，不是多个群机器人入口。',
            '',
        ]
    )


def sanitize_system_understanding_text(text: str) -> tuple[str, int]:
    redacted_count = 0
    text = _PRIVATE_KEY_BLOCK_PATTERN.sub('【敏感私钥块已脱敏】', str(text or ''))
    text = _DINGTALK_WEBHOOK_PATTERN.sub('【钉钉 webhook 已脱敏】', text)
    text = _BEARER_PATTERN.sub('Authorization 已脱敏', text)
    text = _CONNECTION_AUTH_PATTERN.sub(r'\1<redacted>:<redacted>@', text)

    safe_lines: list[str] = []
    for raw_line in text.splitlines():
        line = redact_secret_text(raw_line)
        if _SENSITIVE_LINE_PATTERN.search(line):
            cleaned = _ASSIGNMENT_PATTERN.sub(' 已脱敏', line)
            if cleaned != line:
                redacted_count += 1
                line = cleaned
            if _looks_like_secret_bearing_line(line):
                redacted_count += 1
                line = '【敏感配置行已脱敏】'
        safe_lines.append(line)

    safe_text = build_factory_profile_memory() + '\n'.join(safe_lines)
    return safe_text, redacted_count


def write_safe_system_understanding_copy(
    *,
    source_path: str | Path,
    output_path: str | Path | None = None,
) -> SafeDocumentResult:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(str(source))
    output = Path(output_path) if output_path else source.with_name(SAFE_SYSTEM_UNDERSTANDING_FILENAME)
    original_text = source.read_text(encoding='utf-8', errors='replace')
    safe_text, redacted_count = sanitize_system_understanding_text(original_text)
    output.write_text(safe_text, encoding='utf-8')
    return SafeDocumentResult(
        source_path=str(source),
        output_path=str(output),
        redacted_line_count=redacted_count,
        original_size=len(original_text),
        safe_size=len(safe_text),
    )


def ensure_factory_controller_profile(db: Session, *, apply: bool = True) -> dict[str, Any]:
    payload = {
        'code': FACTORY_PROFILE_CODE,
        'name': FACTORY_PROFILE_NAME,
        'agent_type': 'factory_controller',
        'scope_type': 'factory',
        'config_payload': {
            'managed_by': 'hermes_governance',
            'entrypoint': 'dingtalk_hermes',
            'uses_data_center_cli': True,
            'legacy_memory_policy': 'exclude_from_factory_answers',
            'requires_outbox': True,
            'direct_production_write_allowed': False,
        },
    }
    if not apply:
        return {'applied': False, 'profile': payload}
    agent = db.query(AgentProfile).filter(AgentProfile.code == FACTORY_PROFILE_CODE).first()
    if agent is None:
        agent = AgentProfile(code=FACTORY_PROFILE_CODE, name=FACTORY_PROFILE_NAME)
        db.add(agent)
    agent.name = FACTORY_PROFILE_NAME
    agent.agent_type = 'factory_controller'
    agent.scope_type = 'factory'
    agent.workshop_id = None
    agent.team_id = None
    agent.is_active = True
    agent.config_payload = payload['config_payload']
    db.flush()
    return {'applied': True, 'profile_id': agent.id, 'profile': payload}


def apply_legacy_agent_governance(db: Session, *, apply: bool = True) -> dict[str, Any]:
    agents = db.query(AgentProfile).order_by(AgentProfile.id.asc()).all()
    channels = db.query(CommunicationChannel).order_by(CommunicationChannel.id.asc()).all()
    bindings = db.query(AgentChannelBinding).all()
    outbox_counts = {
        str(status): int(count)
        for status, count in db.query(AgentOutboxMessage.status, func.count(AgentOutboxMessage.id)).group_by(AgentOutboxMessage.status).all()
    }

    if apply:
        ensure_factory_controller_profile(db, apply=True)
        for agent in agents:
            if agent.code == FACTORY_PROFILE_CODE:
                continue
            payload = dict(agent.config_payload or {})
            payload.update(
                {
                    'hermes_governance_role': 'backend_tool',
                    'direct_chat_entry': False,
                    'triggered_by': 'hermes_cli_or_approval',
                    'requires_outbox': True,
                    'legacy_policy': 'preserve_active_backend_tool',
                }
            )
            agent.config_payload = filter_sensitive_mapping(payload)
            agent.is_active = True
        for channel in channels:
            metadata = dict(channel.metadata_payload or {})
            metadata.update(
                {
                    'hermes_governance_role': 'backend_tool_channel',
                    'real_send_enabled': bool(not channel.dry_run),
                    'preserve_dry_run': bool(channel.dry_run),
                }
            )
            channel.metadata_payload = filter_sensitive_mapping(metadata)
        db.flush()

    return {
        'applied': bool(apply),
        'agent_total': len(agents),
        'channel_total': len(channels),
        'binding_total': len(bindings),
        'outbox_status_counts': outbox_counts,
        'factory_profile_code': FACTORY_PROFILE_CODE,
    }


def _looks_like_secret_bearing_line(line: str) -> bool:
    if '已脱敏' in line or 'redacted' in line.lower():
        return False
    if not _SENSITIVE_LINE_PATTERN.search(line):
        return False
    return bool(re.search(r'(?i)[a-z0-9_\-]{20,}', line))
