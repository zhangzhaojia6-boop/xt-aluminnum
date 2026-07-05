from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.database import get_db
from app.main import app
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentOutboxMessage,
    AgentProfile,
    AgentRun,
    ChatInboxMessage,
    CommunicationChannel,
    MultimodalEvidence,
)
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.reports import DailyReport
from app.models.system import User
from app.routers import dingtalk as dingtalk_router
from app.services.agent_command_service import AgentCommandError
from app.services.rag_service import create_document_from_bytes


DINGTALK_AGENT_TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    AgentProfile.__table__,
    CommunicationChannel.__table__,
    AgentChannelBinding.__table__,
    AgentOutboxMessage.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
    MultimodalEvidence.__table__,
    DailyReport.__table__,
]


def _install_db_override():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=DINGTALK_AGENT_TABLES)
    db = Session(engine)

    def fake_get_db():
        yield db

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    return db, previous_overrides


def _restore_db_override(previous_overrides, db: Session) -> None:
    db.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_dingtalk_agent_inbound_forwards_bound_manager_message_to_agent(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        )
    )
    db.commit()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'factory_total': {
                'daily_output': 42.5,
                'packaging_output': 42.5,
                'finished_inbound_output': 39.25,
                'daily_output_source': 'mes_stock_records',
                'finished_inbound_source': 'storage_owner_daily_entry',
                'business_day_start': '07:50',
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.agent_command_service.realtime_service.build_live_aggregation',
        fake_live_aggregation,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-production-test',
                'conversationType': 'group',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@鑫泰助手 /今日产量'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-inbound-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['errcode'] == 0
        assert payload['trace_id'] == 'trace-dingtalk-inbound-001'
        assert payload['intent'] == 'production_today'
        assert '包装产量 42.50 吨' in payload['answer']

        inbox = db.query(ChatInboxMessage).one()
        assert inbox.channel == 'dingtalk_group'
        assert inbox.group_id == 'cid-production-test'
        assert inbox.sender_external_id == 'dt-manager-001'
        assert inbox.text == '@鑫泰助手 /今日产量'
        assert 'sessionWebhook' not in inbox.source_payload

        run = db.query(AgentRun).one()
        assert run.trace_id == 'trace-dingtalk-inbound-001'
        assert run.result_payload['intent'] == 'production_today'
        assert run.result_payload['interpreted_text'] == '今日产量'
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_records_private_message_as_private_channel(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=11,
            username='manager-private',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-private-001',
            dingtalk_union_id='union-manager-private-001',
        )
    )
    db.commit()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'factory_total': {
                'daily_output': 42.5,
                'packaging_output': 42.5,
                'finished_inbound_output': 39.25,
                'daily_output_source': 'mes_stock_records',
                'finished_inbound_source': 'storage_owner_daily_entry',
                'business_day_start': '07:50',
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.agent_command_service.realtime_service.build_live_aggregation',
        fake_live_aggregation,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-private-001',
                'conversationType': '1',
                'senderStaffId': 'dt-manager-private-001',
                'senderUnionId': 'union-manager-private-001',
                'text': {'content': '今日产量'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-private-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['errcode'] == 0
        assert payload['trace_id'] == 'trace-dingtalk-private-001'

        inbox = db.query(ChatInboxMessage).one()
        assert inbox.channel == 'dingtalk_private'
        assert inbox.group_id == 'cid-private-001'
        run = db.query(AgentRun).one()
        assert run.trace_id == 'trace-dingtalk-private-001'
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_records_file_only_evidence_without_running_agent(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=12,
            username='energy-file-manager',
            password_hash='x',
            name='能耗负责人',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-energy-file-001',
            dingtalk_union_id='union-energy-file-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-energy-files',
                'conversationType': 'group',
                'senderStaffId': 'dt-energy-file-001',
                'senderUnionId': 'union-energy-file-001',
                'msgtype': 'file',
                'fileName': '7月5日抄表.xlsx',
                'mediaId': 'media-energy-20260705',
                'traceId': 'trace-dingtalk-file-only-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['action'] == 'dingtalk-evidence-recorded'
        assert payload['should_reply'] is False
        assert payload['chat_inbox_id'] is None
        assert payload['agent_run_id'] is None
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0

        evidence = db.query(MultimodalEvidence).one()
        assert payload['evidence_id'] == evidence.id
        assert evidence.evidence_type == 'attachment'
        assert evidence.file_uri == 'dingtalk://media/media-energy-20260705'
        assert evidence.payload['channel'] == 'dingtalk_group'
        assert evidence.payload['group_id'] == 'cid-energy-files'
        assert evidence.payload['file_name'] == '7月5日抄表.xlsx'
        assert evidence.payload['evidence_kind'] == 'fact'
        assert evidence.payload['metric_write_allowed'] is False
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_keeps_private_channel_when_conversation_id_exists_without_group_type(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=14,
            username='manager-private-conversation',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-private-conversation-001',
            dingtalk_union_id='union-manager-private-conversation-001',
        )
    )
    db.commit()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'factory_total': {
                'daily_output': 42.5,
                'packaging_output': 42.5,
                'finished_inbound_output': 39.25,
                'daily_output_source': 'mes_stock_records',
                'finished_inbound_source': 'storage_owner_daily_entry',
                'business_day_start': '07:50',
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.agent_command_service.realtime_service.build_live_aggregation',
        fake_live_aggregation,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-private-with-conversation-id',
                'senderStaffId': 'dt-manager-private-conversation-001',
                'senderUnionId': 'union-manager-private-conversation-001',
                'text': {'content': '今日产量'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-private-conversation-id-001',
            },
        )

        assert response.status_code == 200
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.channel == 'dingtalk_private'
        assert inbox.group_id == 'cid-private-with-conversation-id'
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_queues_reply_when_group_channel_is_bound_by_default(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add_all([
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        ),
        AgentProfile(
            id=1,
            code='factory_dispatch',
            name='全厂总控 Agent',
            agent_type='reporting',
            scope_type='factory',
            is_active=True,
        ),
        CommunicationChannel(
            id=1,
            channel_type='dingtalk_group',
            channel_key='cid-production-test',
            name='生产总控测试群',
            target_type='factory',
            target_key='factory',
            dry_run=True,
            is_active=True,
        ),
        AgentChannelBinding(
            agent_profile_id=1,
            channel_id=1,
            is_active=True,
            min_severity='info',
        ),
    ])
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-production-test',
                'conversationType': 'group',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@鑫泰助手 点检资料怎么查'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-inbound-auto-outbox-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['outbox_message_id'] is not None

        message = db.get(AgentOutboxMessage, payload['outbox_message_id'])
        assert message is not None
        assert message.status == 'pending'
        assert message.trace_id == 'trace-dingtalk-inbound-auto-outbox-001'
        assert message.content == payload['answer']
        assert message.payload['chat_inbox_id'] == payload['chat_inbox_id']
        assert db.query(AgentOutboxMessage).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_scopes_rag_by_bound_channel_workshop(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add_all([
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        ),
        Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
        CommunicationChannel(
            channel_type='dingtalk_group',
            channel_key='cid-hot-roll',
            name='热轧状态群',
            target_type='workshop',
            target_key='热轧',
            workshop_id=10,
            dry_run=True,
            is_active=True,
            metadata_payload={'machine_code': 'RZ-1'},
        ),
    ])
    create_document_from_bytes(
        db,
        filename='冷轧点检标准.md',
        content=('点检标准要求先确认张力记录，再核对冷轧油路压力。' * 20).encode('utf-8'),
        content_type='text/markdown',
        uploaded_by=None,
        source_name='冷轧点检标准',
        metadata={'workshop': '冷轧2050', 'machine_code': 'LZ2050-9'},
    )
    create_document_from_bytes(
        db,
        filename='热轧1号机点检标准.md',
        content=('点检标准要求先确认轧辊温度，再核对热轧液压压力。' * 20).encode('utf-8'),
        content_type='text/markdown',
        uploaded_by=None,
        source_name='热轧1号机点检标准',
        metadata={'workshop': '热轧', 'machine_code': 'RZ-1'},
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-hot-roll',
                'conversationType': 'group',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@鑫泰助手 点检标准怎么做'},
                'agentCode': 'maintenance_agent',
                'traceId': 'trace-dingtalk-inbound-rag-scope-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert '热轧1号机点检标准.md' in payload['answer']
        assert '冷轧点检标准.md' not in payload['answer']

        run = db.query(AgentRun).one()
        assert run.result_payload['rag']['scope'] == {'workshop': '热轧', 'machine_code': 'RZ-1'}
        assert run.result_payload['rag']['citations'][0]['filename'] == '热轧1号机点检标准.md'
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_rejects_channel_outside_user_workshop(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add_all([
        User(
            id=2,
            username='cold_director',
            password_hash='x',
            name='冷轧主任',
            role='workshop_director',
            is_manager=True,
            is_reviewer=True,
            workshop_id=20,
            is_active=True,
            dingtalk_user_id='dt-cold-director-001',
            dingtalk_union_id='union-cold-director-001',
        ),
        Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
        Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        CommunicationChannel(
            channel_type='dingtalk_group',
            channel_key='cid-hot-roll',
            name='热轧状态群',
            target_type='workshop',
            target_key='热轧',
            workshop_id=10,
            dry_run=True,
            is_active=True,
        ),
    ])
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-hot-roll',
                'conversationType': 'group',
                'senderStaffId': 'dt-cold-director-001',
                'senderUnionId': 'union-cold-director-001',
                'text': {'content': '@鑫泰助手 点检标准怎么做'},
                'agentCode': 'maintenance_agent',
                'traceId': 'trace-dingtalk-inbound-denied-001',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'dingtalk_channel_scope_denied'
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_rejects_missing_token_when_configured(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            json={
                'conversationId': 'cid-production-test',
                'senderStaffId': 'dt-manager-001',
                'text': {'content': '今日产量'},
            },
        )

        assert response.status_code == 401
        assert response.json()['detail'] == 'dingtalk_inbound_token_invalid'
        assert db.query(ChatInboxMessage).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_disabled_does_not_write_report_or_run(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=12,
            username='root-owner-disabled',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root-disabled-001',
            dingtalk_union_id='union-root-disabled-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', False, raising=False)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root-disabled-001')

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-root-disabled-001',
                'senderUnionId': 'union-root-disabled-001',
                'text': {'content': '生成 6月19日正式日报'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-day1-disabled-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['errcode'] == 0
        assert payload['status'] == 'disabled'
        assert payload['code'] == 'hermes_day1_disabled'
        assert payload['trace_id'] == 'trace-dingtalk-day1-disabled-001'
        assert '未开启' in payload['answer'] or '已关闭' in payload['answer']
        assert payload['agent_run_id'] is None
        assert payload['report_id'] is None
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
        assert db.query(DailyReport).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_disabled_still_allows_normal_messages(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=15,
            username='manager-disabled-normal',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-disabled-normal-001',
            dingtalk_union_id='union-manager-disabled-normal-001',
        )
    )
    db.commit()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'factory_total': {
                'daily_output': 42.5,
                'packaging_output': 42.5,
                'finished_inbound_output': 39.25,
                'daily_output_source': 'mes_stock_records',
                'finished_inbound_source': 'storage_owner_daily_entry',
                'business_day_start': '07:50',
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', False, raising=False)
    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.agent_command_service.realtime_service.build_live_aggregation',
        fake_live_aggregation,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-manager-disabled-normal-001',
                'senderUnionId': 'union-manager-disabled-normal-001',
                'text': {'content': '今日产量'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-disabled-normal-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'answered'
        assert payload['intent'] == 'production_today'
        assert db.query(ChatInboxMessage).count() == 1
        assert db.query(AgentRun).count() == 1
        assert db.query(DailyReport).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_accepts_hermes_token_without_replacing_legacy_token(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'legacy-inbound', raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-inbound', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-inbound'},
            json={
                'conversationId': 'cid-hermes-test',
                'conversationType': 'group',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@Hermes 点检资料怎么查'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-hermes-token-001',
            },
        )

        assert response.status_code == 200
        assert response.json()['trace_id'] == 'trace-hermes-token-001'
        assert db.query(ChatInboxMessage).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_hermes_dingtalk_inbound_alias_reuses_agent_inbound_contract(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', '', raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-inbound', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/hermes/dingtalk/inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-inbound'},
            json={
                'conversationId': 'cid-hermes-test',
                'conversationType': 'group',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@Hermes 点检资料怎么查'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-hermes-alias-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['errcode'] == 0
        assert payload['trace_id'] == 'trace-hermes-alias-001'
        assert db.query(ChatInboxMessage).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_redacts_agent_error_detail(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        )
    )
    db.commit()

    def fake_handle_agent_command(*_args, **_kwargs):
        raise AgentCommandError('agent failed password=detail-pass token=detail-token')

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router, 'handle_agent_command', fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-production-test',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@鑫泰助手 今日产量'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-redacted-error-001',
            },
        )

        assert response.status_code == 400
        detail = response.json()['detail']
        assert 'detail-pass' not in detail
        assert 'detail-token' not in detail
        assert detail == 'agent failed password=<redacted> token=<redacted>'
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_root_owner_calls_orchestrator_without_forcing_noise_evidence(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=13,
            username='root-owner-ready',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root-ready-001',
            dingtalk_union_id='union-root-ready-001',
        )
    )
    db.commit()

    seen: dict[str, object] = {}

    def fake_record_day1_dingtalk_evidence(*_args, **kwargs):
        seen['evidence_channel'] = kwargs['channel']
        seen['evidence_group_id'] = kwargs['group_id']
        seen['recognized_text'] = kwargs['recognized_text']
        return None

    def fake_run_day1_super_brain(_db, *, command, actor, trace_id, chat_inbox):
        seen['business_date'] = command.business_date.isoformat()
        seen['actor_id'] = actor.id
        seen['chat_inbox_id'] = chat_inbox.id
        return type(
            'FakeDay1Result',
            (),
            {
                'trace_id': trace_id,
                'status': 'ready',
                'answer': '6月19日正式日报已生成',
                'reply_messages': ['[1/2] 智能大脑判断单', '[2/2] 正式日报正文'],
                'agent_run_id': 301,
                'report_id': 201,
            },
        )()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', True, raising=False)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root-ready-001')
    monkeypatch.setattr(dingtalk_router, 'record_day1_dingtalk_evidence', fake_record_day1_dingtalk_evidence)
    monkeypatch.setattr(dingtalk_router, 'run_day1_super_brain', fake_run_day1_super_brain)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-root-ready-001',
                'senderUnionId': 'union-root-ready-001',
                'text': {'content': '生成 6月19日正式日报'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-day1-ready-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['errcode'] == 0
        assert payload['status'] == 'ready'
        assert payload['answer'] == '6月19日正式日报已生成'
        assert payload['messages'] == ['[1/2] 智能大脑判断单', '[2/2] 正式日报正文']
        assert payload['chat_inbox_id'] == seen['chat_inbox_id']
        assert payload['agent_run_id'] == 301
        assert payload['report_id'] == 201

        inbox = db.get(ChatInboxMessage, payload['chat_inbox_id'])
        assert inbox is not None
        assert inbox.channel == 'dingtalk_private'
        assert inbox.group_id is None
        assert seen == {
            'evidence_channel': 'dingtalk_private',
            'evidence_group_id': None,
            'recognized_text': '生成 6月19日正式日报',
            'business_date': '2026-06-19',
            'actor_id': 13,
            'chat_inbox_id': payload['chat_inbox_id'],
        }
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_rejects_non_root_owner(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=16,
            username='allowed-not-owner',
            password_hash='x',
            name='授权用户',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-allowed-not-owner-001',
            dingtalk_union_id='union-allowed-not-owner-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', True, raising=False)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed-not-owner-001')

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-allowed-not-owner-001',
                'senderUnionId': 'union-allowed-not-owner-001',
                'text': {'content': '生成 6月19日正式日报'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-day1-non-owner-001',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'owner_required'
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
        assert db.query(DailyReport).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_slash_daily_report_stays_on_legacy_handler(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=18,
            username='manager-legacy-slash',
            password_hash='x',
            name='授权用户',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-legacy-slash-001',
            dingtalk_union_id='union-legacy-slash-001',
        )
    )
    db.commit()

    seen: dict[str, object] = {}

    def fake_handle_agent_command(*_args, **kwargs):
        seen['text'] = kwargs['text']
        seen['channel'] = kwargs['channel']
        return type(
            'FakeAgentCommandResult',
            (),
            {
                'trace_id': kwargs['trace_id'],
                'status_color': 'green',
                'intent': 'legacy_daily_report',
                'facts': {},
                'answer': 'legacy /日报 handled',
                'rag': {},
                'chat_inbox_id': 701,
                'agent_run_id': 702,
                'outbox_message_id': None,
            },
        )()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', False, raising=False)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-legacy-slash-001')
    monkeypatch.setattr(dingtalk_router, 'handle_agent_command', fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-legacy-slash-001',
                'senderUnionId': 'union-legacy-slash-001',
                'text': {'content': '/日报 2026-06-19'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-legacy-slash-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'answered'
        assert payload['intent'] == 'legacy_daily_report'
        assert payload['answer'] == 'legacy /日报 handled'
        assert seen == {
            'text': '/日报 2026-06-19',
            'channel': 'dingtalk_private',
        }
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_non_root_owner_persists_evidence_before_403(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=19,
            username='allowed-fact-not-owner',
            password_hash='x',
            name='授权用户',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-allowed-fact-001',
            dingtalk_union_id='union-allowed-fact-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', True, raising=False)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed-fact-001')

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-allowed-fact-001',
                'senderUnionId': 'union-allowed-fact-001',
                'text': {'content': '生成 6月19日正式日报，产量 32 吨'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-day1-fact-403-001',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'owner_required'
        assert db.query(MultimodalEvidence).count() == 1
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['business_date'] == '2026-06-19'
        assert evidence.payload['evidence_kind'] == 'fact'
        assert db.query(DailyReport).count() == 0
        assert db.query(AgentRun).count() == 0
        assert db.query(ChatInboxMessage).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_non_root_owner_dedupes_evidence_only_trace_id(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=191,
            username='allowed-fact-not-owner-duplicate',
            password_hash='x',
            name='授权用户',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-allowed-fact-dup-001',
            dingtalk_union_id='union-allowed-fact-dup-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', True, raising=False)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed-fact-dup-001')

    payload = {
        'senderStaffId': 'dt-allowed-fact-dup-001',
        'senderUnionId': 'union-allowed-fact-dup-001',
        'text': {'content': '生成 6月19日正式日报，产量 32 吨'},
        'agentCode': 'factory_dispatch',
        'traceId': 'trace-dingtalk-day1-fact-403-dup-001',
    }

    try:
        client = TestClient(app)
        first = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )
        second = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )

        assert first.status_code == 403
        assert second.status_code == 403
        assert first.json()['detail'] == 'owner_required'
        assert second.json()['detail'] == 'owner_required'
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_disabled_dedupes_evidence_only_trace_id(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=192,
            username='root-owner-disabled-duplicate',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root-disabled-dup-001',
            dingtalk_union_id='union-root-disabled-dup-001',
        )
    )
    db.commit()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', False, raising=False)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root-disabled-dup-001')

    payload = {
        'senderStaffId': 'dt-root-disabled-dup-001',
        'senderUnionId': 'union-root-disabled-dup-001',
        'text': {'content': '生成 6月19日正式日报，产量 32 吨'},
        'agentCode': 'factory_dispatch',
        'traceId': 'trace-dingtalk-day1-disabled-dup-001',
    }

    try:
        client = TestClient(app)
        first = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )
        second = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()['code'] == 'hermes_day1_disabled'
        assert second.json()['code'] == 'hermes_day1_disabled'
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_authorized_fact_message_records_evidence_then_calls_legacy_agent(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=20,
            username='allowed-fact-message',
            password_hash='x',
            name='授权用户',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-allowed-fact-message-001',
            dingtalk_union_id='union-allowed-fact-message-001',
        )
    )
    db.commit()

    seen: dict[str, object] = {}

    def fake_handle_agent_command(*_args, **kwargs):
        seen['text'] = kwargs['text']
        return type(
            'FakeAgentCommandResult',
            (),
            {
                'trace_id': kwargs['trace_id'],
                'status_color': 'green',
                'intent': 'production_today',
                'facts': {},
                'answer': 'legacy fact handled',
                'rag': {},
                'chat_inbox_id': 801,
                'agent_run_id': 802,
                'outbox_message_id': None,
            },
        )()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed-fact-message-001')
    monkeypatch.setattr(dingtalk_router, 'handle_agent_command', fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-allowed-fact-message-001',
                'senderUnionId': 'union-allowed-fact-message-001',
                'text': {'content': '今日产量 32 吨'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-authorized-fact-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'answered'
        assert payload['answer'] == 'legacy fact handled'
        assert seen['text'] == '今日产量 32 吨'
        assert db.query(MultimodalEvidence).count() == 1
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['evidence_kind'] == 'fact'
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_authorized_noise_message_skips_evidence_and_calls_legacy_agent(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=21,
            username='allowed-noise-message',
            password_hash='x',
            name='授权用户',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-allowed-noise-message-001',
            dingtalk_union_id='union-allowed-noise-message-001',
        )
    )
    db.commit()

    seen: dict[str, object] = {}

    def fake_handle_agent_command(*_args, **kwargs):
        seen['text'] = kwargs['text']
        return type(
            'FakeAgentCommandResult',
            (),
            {
                'trace_id': kwargs['trace_id'],
                'status_color': 'green',
                'intent': 'noise_reply',
                'facts': {},
                'answer': 'legacy noise handled',
                'rag': {},
                'chat_inbox_id': 901,
                'agent_run_id': 902,
                'outbox_message_id': None,
            },
        )()

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed-noise-message-001')
    monkeypatch.setattr(dingtalk_router, 'handle_agent_command', fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'senderStaffId': 'dt-allowed-noise-message-001',
                'senderUnionId': 'union-allowed-noise-message-001',
                'text': {'content': '收到，谢谢'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-authorized-noise-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'answered'
        assert payload['answer'] == 'legacy noise handled'
        assert seen['text'] == '收到，谢谢'
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['evidence_kind'] == 'noise'
        assert evidence.payload['include_in_daily_sample'] is False
        assert evidence.payload['metric_write_allowed'] is False
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_treats_string_false_as_no_outbox(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        )
    )
    db.commit()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'factory_total': {
                'daily_output': 42.5,
                'finished_inbound_output': 39.25,
                'daily_output_source': 'mes_stock_records',
                'finished_inbound_source': 'storage_owner_daily_entry',
                'business_day_start': '07:50',
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.agent_command_service.realtime_service.build_live_aggregation',
        fake_live_aggregation,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-production-test',
                'senderStaffId': 'dt-manager-001',
                'senderUnionId': 'union-manager-001',
                'text': {'content': '@鑫泰助手 今日产量'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-inbound-002',
                'queueOutbox': 'false',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['outbox_message_id'] is None
        assert payload['intent'] == 'production_today'
        assert db.query(ChatInboxMessage).count() == 1
        assert db.query(AgentRun).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_dedupes_same_message_trace_id(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-001',
            dingtalk_union_id='union-manager-001',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        payload = {
            'conversationId': 'cid-production-test',
            'conversationType': 'group',
            'senderStaffId': 'dt-manager-001',
            'senderUnionId': 'union-manager-001',
            'text': {'content': '@鑫泰助手 今日产量'},
            'agentCode': 'factory_dispatch',
            'traceId': 'trace-dingtalk-dedupe-001',
            'queueOutbox': 'false',
        }
        first = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )
        second = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        duplicate = second.json()
        assert duplicate['action'] == 'dingtalk-duplicate'
        assert duplicate['should_reply'] is False
        assert db.query(ChatInboxMessage).count() == 1
        assert db.query(AgentRun).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_duplicate_chat_message_does_not_duplicate_evidence(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=193,
            username='manager-dedupe-evidence',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-dedupe-evidence-001',
            dingtalk_union_id='union-manager-dedupe-evidence-001',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)

    try:
        client = TestClient(app)
        payload = {
            'conversationId': 'cid-dedupe-evidence-test',
            'conversationType': 'group',
            'senderStaffId': 'dt-manager-dedupe-evidence-001',
            'senderUnionId': 'union-manager-dedupe-evidence-001',
            'text': {'content': '今日产量 32 吨'},
            'agentCode': 'factory_dispatch',
            'traceId': 'trace-dingtalk-chat-evidence-dedupe-001',
            'queueOutbox': 'false',
        }
        first = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )
        second = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json=payload,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()['action'] == 'dingtalk-duplicate'
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_root_owner_private_uses_production_loop_for_soft_message(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=88,
            username="root-owner-soft",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-soft-001",
            dingtalk_union_id="union-root-soft-001",
        )
    )
    db.commit()
    seen = {}

    def fake_turn(_db, **kwargs):
        seen.update(kwargs)
        return type(
            "FakeRootOwnerTurn",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status": "answered",
                "answer": "今天整体正常，已按钉钉事实源回答。",
                "chat_inbox_id": 301,
                "agent_run_id": 401,
                "outbox_message_id": 501,
                "dispatch_status": "sent",
                "dispatch_detail": "sent",
            },
        )()

    def fail_factory_brain_turn(*_args, **_kwargs):
        raise AssertionError("root_owner private soft message should not reach 智能大脑主链路")

    def fail_fallback(*_args, **_kwargs):
        raise AssertionError("root_owner private soft message should not reach fallback")

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setattr("app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-soft-001")
    monkeypatch.setattr(dingtalk_router, "run_root_owner_production_turn", fake_turn)
    monkeypatch.setattr(
        "app.services.hermes_factory_brain_orchestrator.run_factory_brain_turn",
        fail_factory_brain_turn,
    )
    monkeypatch.setattr(dingtalk_router, "handle_agent_command", fail_fallback)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-soft-001",
                "senderUnionId": "union-root-soft-001",
                "text": {"content": "今天咋样"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-soft-route-001",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent_code"] == "factory_dispatch"
        assert payload["status"] == "answered"
        assert payload["answer"] == "今天整体正常，已按钉钉事实源回答。"
        assert payload["outbox_message_id"] == 501
        assert payload["dispatch_status"] == "sent"
        assert seen["text"] == "今天咋样"
        assert seen["sender_external_id"] == "dt-root-soft-001"
        assert seen["trace_id"] == "trace-root-soft-route-001"
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_root_owner_private_ambiguous_follow_up_uses_production_loop(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=94,
            username="root-owner-ambiguous-follow-up",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-ambiguous-follow-up-001",
            dingtalk_union_id="union-root-ambiguous-follow-up-001",
        )
    )
    db.commit()
    seen = {}

    def fake_turn(_db, **kwargs):
        seen.update(kwargs)
        return type(
            "FakeRootOwnerTurn",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status": "clarifying",
                "answer": "你想看哪一天的哪类生产数据？",
                "chat_inbox_id": 303,
                "agent_run_id": 403,
                "outbox_message_id": 503,
                "dispatch_status": "sent",
                "dispatch_detail": "sent",
            },
        )()

    def fail_fallback(*_args, **_kwargs):
        raise AssertionError("ambiguous root_owner private follow-up should not reach fallback")

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-ambiguous-follow-up-001")
    monkeypatch.setattr(dingtalk_router, "run_root_owner_production_turn", fake_turn)
    monkeypatch.setattr(dingtalk_router, "handle_agent_command", fail_fallback)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-ambiguous-follow-up-001",
                "senderUnionId": "union-root-ambiguous-follow-up-001",
                "text": {"content": "昨天呢"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-ambiguous-follow-up-route-001",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "clarifying"
        assert payload["answer"] == "你想看哪一天的哪类生产数据？"
        assert payload["outbox_message_id"] == 503
        assert seen["text"] == "昨天呢"
        assert seen["sender_external_id"] == "dt-root-ambiguous-follow-up-001"
        assert seen["trace_id"] == "trace-root-ambiguous-follow-up-route-001"
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_parse_error_does_not_hard_fail_for_root_owner_private(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=89,
            username="root-owner-invalid-date",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-invalid-date-001",
            dingtalk_union_id="union-root-invalid-date-001",
        )
    )
    db.commit()
    seen = {}

    def fake_turn(_db, **kwargs):
        seen.update(kwargs)
        return type(
            "FakeRootOwnerTurn",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status": "clarifying",
                "answer": "你想看哪一天的日报或生产情况？",
                "chat_inbox_id": 302,
                "agent_run_id": 402,
                "outbox_message_id": 502,
                "dispatch_status": "sent",
                "dispatch_detail": "sent",
            },
        )()

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-invalid-date-001")
    monkeypatch.setattr(dingtalk_router, "run_root_owner_production_turn", fake_turn)
    monkeypatch.setattr("app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED", True, raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-invalid-date-001",
                "senderUnionId": "union-root-invalid-date-001",
                "text": {"content": "生成 13月99日正式日报"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-invalid-date-route-001",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "clarifying"
        assert response.json()["answer"] == "你想看哪一天的日报或生产情况？"
        assert seen["source_payload"]["day1_parse_error"] == "invalid_date"
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_parse_error_returns_400_outside_root_owner_private_loop(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add_all([
        User(
            id=90,
            username="manager-invalid-date",
            password_hash="x",
            name="生产经理",
            role="manager",
            is_manager=True,
            is_active=True,
            dingtalk_user_id="dt-manager-invalid-date-001",
            dingtalk_union_id="union-manager-invalid-date-001",
        ),
        User(
            id=91,
            username="root-owner-group-invalid-date",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-group-invalid-date-001",
            dingtalk_union_id="union-root-group-invalid-date-001",
        ),
    ])
    db.commit()

    def fail_factory_brain_turn(*_args, **_kwargs):
        raise AssertionError("Day1 parse error should not reach 智能大脑主链路 outside root_owner private loop")

    def fail_fallback(*_args, **_kwargs):
        raise AssertionError("Day1 parse error should not reach fallback outside root_owner private loop")

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setattr("app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-group-invalid-date-001")
    monkeypatch.setattr(
        "app.services.hermes_factory_brain_orchestrator.run_factory_brain_turn",
        fail_factory_brain_turn,
    )
    monkeypatch.setattr(dingtalk_router, "handle_agent_command", fail_fallback)

    try:
        client = TestClient(app)
        non_root_response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-manager-invalid-date-001",
                "senderUnionId": "union-manager-invalid-date-001",
                "text": {"content": "生成 13月99日正式日报"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-manager-invalid-date-route-001",
            },
        )
        group_response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "conversationId": "cid-root-invalid-date-group",
                "conversationType": "group",
                "senderStaffId": "dt-root-group-invalid-date-001",
                "senderUnionId": "union-root-group-invalid-date-001",
                "text": {"content": "生成 13月99日正式日报"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-group-invalid-date-route-001",
            },
        )

        assert non_root_response.status_code == 400
        assert non_root_response.json()["detail"] == "invalid_date"
        assert group_response.status_code == 400
        assert group_response.json()["detail"] == "invalid_date"
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_root_owner_private_slash_commands_use_legacy_fallback(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=92,
            username="root-owner-slash-command",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-slash-command-001",
            dingtalk_union_id="union-root-slash-command-001",
        )
    )
    db.commit()
    seen: dict[str, object] = {}

    def fail_root_owner_turn(*_args, **_kwargs):
        raise AssertionError("root_owner private slash command should not reach production loop")

    def fake_handle_agent_command(*_args, **kwargs):
        seen["text"] = kwargs["text"]
        return type(
            "FakeAgentCommandResult",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status_color": "green",
                "intent": "help",
                "facts": {},
                "answer": "旧 /commands fallback",
                "rag": {},
                "chat_inbox_id": 911,
                "agent_run_id": 912,
                "outbox_message_id": None,
            },
        )()

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setattr("app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-slash-command-001")
    monkeypatch.setattr(dingtalk_router, "run_root_owner_production_turn", fail_root_owner_turn)
    monkeypatch.setattr(dingtalk_router, "handle_agent_command", fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-slash-command-001",
                "senderUnionId": "union-root-slash-command-001",
                "text": {"content": "/commands"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-slash-command-route-001",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] == "help"
        assert payload["answer"] == "旧 /commands fallback"
        assert seen["text"] == "/commands"
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_root_owner_private_joke_uses_legacy_fallback(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=93,
            username="root-owner-joke",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-joke-001",
            dingtalk_union_id="union-root-joke-001",
        )
    )
    db.commit()
    seen: dict[str, object] = {}

    def fail_root_owner_turn(*_args, **_kwargs):
        raise AssertionError("root_owner private general chat should not reach production loop")

    def fake_handle_agent_command(*_args, **kwargs):
        seen["text"] = kwargs["text"]
        return type(
            "FakeAgentCommandResult",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status_color": "green",
                "intent": "general_chat",
                "facts": {},
                "answer": "旧闲聊 fallback",
                "rag": {},
                "chat_inbox_id": 921,
                "agent_run_id": 922,
                "outbox_message_id": None,
            },
        )()

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setattr("app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-joke-001")
    monkeypatch.setattr(dingtalk_router, "run_root_owner_production_turn", fail_root_owner_turn)
    monkeypatch.setattr(dingtalk_router, "handle_agent_command", fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-joke-001",
                "senderUnionId": "union-root-joke-001",
                "text": {"content": "给我讲个轻松的笑话"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-joke-route-001",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] == "general_chat"
        assert payload["answer"] == "旧闲聊 fallback"
        assert seen["text"] == "给我讲个轻松的笑话"
    finally:
        _restore_db_override(previous_overrides, db)
