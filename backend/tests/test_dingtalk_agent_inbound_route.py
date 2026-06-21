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
                'text': {'content': '@鑫泰助手 今日产量'},
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
        assert inbox.text == '@鑫泰助手 今日产量'
        assert 'sessionWebhook' not in inbox.source_payload

        run = db.query(AgentRun).one()
        assert run.trace_id == 'trace-dingtalk-inbound-001'
        assert run.result_payload['intent'] == 'production_today'
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
                'reply_messages': ['[1/2] 工厂大脑判断单', '[2/2] 正式日报正文'],
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
        assert payload['messages'] == ['[1/2] 工厂大脑判断单', '[2/2] 正式日报正文']
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
