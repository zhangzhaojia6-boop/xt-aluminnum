from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.agent_communication import AgentChannelBinding, AgentOutboxMessage, AgentProfile, CommunicationChannel
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagEmbedding, RagQueryLog, RagSourceIngestion
from app.models.system import User
from app.services import hermes_governance_service, hermes_rag_service
from app.services.rag_service import query_knowledge


RAG_TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    RagEmbedding.__table__,
    RagSourceIngestion.__table__,
]


def _session(tmp_path, tables):
    engine = create_engine(f"sqlite:///{tmp_path / 'hermes-governance.db'}", future=True)
    Base.metadata.create_all(engine, tables=tables)
    return Session(engine)


def test_safe_system_understanding_copy_can_be_ingested_without_secret_values(tmp_path) -> None:
    db = _session(tmp_path, RAG_TABLES)
    source = tmp_path / 'system-understanding.md'
    safe = tmp_path / 'system-understanding.rag-safe.md'
    source.write_text(
        '\n'.join(
            [
                '# 系统理解',
                '日报口径：每日 7:30 生成前一个业务日。',
                'DINGTALK_CLIENT_SECRET=real-secret-value-1234567890',
                '数据库密码：real-db-password-1234567890',
                'webhook=https://oapi.dingtalk.com/robot/send?access_token=abc1234567890',
                '-----BEGIN PRIVATE KEY-----',
                'private-key-body',
                '-----END PRIVATE KEY-----',
                '包装产量来自 WMS_InStock.TotalNetWeight + InStockDate。',
            ]
        ),
        encoding='utf-8',
    )

    try:
        result = hermes_governance_service.write_safe_system_understanding_copy(
            source_path=source,
            output_path=safe,
        )
        safe_text = safe.read_text(encoding='utf-8')

        assert result.redacted_line_count >= 3
        assert 'real-secret-value' not in safe_text
        assert 'real-db-password' not in safe_text
        assert 'access_token=' not in safe_text
        assert 'BEGIN PRIVATE KEY' not in safe_text
        assert 'END PRIVATE KEY' not in safe_text
        assert '鑫泰铝业智能大脑' in safe_text

        document = hermes_rag_service.ingest_file(
            db,
            path=safe,
            source_type='internal_system_understanding',
            metadata={'review_status': 'approved', 'temporal_scope': 'stable_knowledge'},
        )
        assert document.status == 'active'
        assert document.metadata_payload['source_type'] == 'internal_system_understanding'

        payload = query_knowledge(db, query='包装产量 WMS_InStock InStockDate', limit=5)
        assert 'WMS_InStock' in payload['answer']
        assert 'real-secret-value' not in payload['answer']
    finally:
        db.close()


def test_legacy_agent_governance_marks_agents_as_backend_tools_without_disabling_dry_run() -> None:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    db = SessionLocal()
    try:
        agent = AgentProfile(
            code='daily_report_secretary_zzj',
            name='张兆嘉日报秘书 Agent',
            agent_type='reporting',
            scope_type='user',
            is_active=True,
            config_payload={'owner_name': '张兆嘉'},
        )
        channel = CommunicationChannel(
            channel_type='dingtalk_group',
            channel_key='hermes-management-dry-run-channel',
            name='Hermes 管理层 dry-run',
            target_type='management',
            dry_run=True,
            is_active=True,
            metadata_payload={'existing': 'keep'},
        )
        db.add_all([agent, channel])
        db.flush()
        db.add(AgentChannelBinding(agent_profile_id=agent.id, channel_id=channel.id, is_active=True))
        db.add(
            AgentOutboxMessage(
                dispatch_key='agent:test',
                agent_profile_id=agent.id,
                channel_id=channel.id,
                status='dry_run',
                title='测试',
                content='测试',
                trace_id='trace-test',
            )
        )
        db.commit()

        outcome = hermes_governance_service.apply_legacy_agent_governance(db, apply=True)
        db.commit()
        db.refresh(agent)
        db.refresh(channel)
        factory = db.query(AgentProfile).filter(AgentProfile.code == 'xt-factory-controller').one()

        assert outcome['applied'] is True
        assert agent.is_active is True
        assert agent.config_payload['hermes_governance_role'] == 'backend_tool'
        assert agent.config_payload['direct_chat_entry'] is False
        assert channel.dry_run is True
        assert channel.metadata_payload['existing'] == 'keep'
        assert channel.metadata_payload['hermes_governance_role'] == 'backend_tool_channel'
        assert channel.metadata_payload['real_send_enabled'] is False
        assert factory.agent_type == 'factory_controller'
    finally:
        db.close()
