from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models import Base
from app.models.system import User
from app.services import agent_communication_service


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'agent-management.db'}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _user(role: str) -> User:
    return User(
        id=1,
        username=f'{role}_user',
        password_hash='test',
        name='测试用户',
        role=role,
        data_scope_type='all' if role == 'admin' else 'self_workshop',
        is_active=True,
    )


def _client(session_factory, current_user: User | None):
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_agent_management_overview_route_allows_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('admin'))
    try:
        response = client.get('/api/v1/agent-management/overview')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['safe_mode'] is True
    assert payload['summary']['agent_total'] == 0
    assert payload['summary']['knowledge_entry_total'] >= 1
    assert payload['knowledge_entries']


def test_agent_management_overview_route_rejects_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.get('/api/v1/agent-management/overview')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()['detail'] == 'Agent management access denied'


def test_agent_management_overview_route_requires_login(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, None)
    try:
        response = client.get('/api/v1/agent-management/overview')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_agent_management_knowledge_routes_answer_with_sources_for_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('admin'))
    try:
        list_response = client.get('/api/v1/agent-management/knowledge')
        answer_response = client.post(
            '/api/v1/agent-management/knowledge/answer',
            json={'question': '全厂总产量和MES包装产量是什么关系？'},
        )
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()['total'] >= 1
    assert answer_response.status_code == 200
    payload = answer_response.json()
    assert payload['can_answer'] is True
    assert payload['citations']
    assert '实时数值' not in payload['answer']


def test_agent_management_knowledge_routes_reject_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.get('/api/v1/agent-management/knowledge')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_agent_management_can_dispatch_dry_run_outbox_and_read_logs(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    db = session_factory()
    try:
        agent_communication_service.register_agent(db, code='factory_dispatch', name='全厂总控 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-prod-secret-001',
            name='测试总控群',
            target_type='management',
            target_key='management',
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-001',
        )
        message = agent_communication_service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-001',
            title='测试消息',
            content='dry-run 消息，不应该真实发送。',
            source_summary='unit_test',
            trace_id='trace-router-dispatch',
        )
    finally:
        db.close()

    client = _client(session_factory, _user('admin'))
    try:
        dispatch_response = client.post(f'/api/v1/agent-management/outbox/{message.id}/dispatch')
        logs_response = client.get(f'/api/v1/agent-management/outbox/{message.id}/logs')
    finally:
        app.dependency_overrides.clear()

    assert dispatch_response.status_code == 200
    dispatch_payload = dispatch_response.json()
    assert dispatch_payload == {
        'outbox_message_id': message.id,
        'status': 'dry_run',
        'detail': 'dry-run only, message not sent',
    }

    assert logs_response.status_code == 200
    logs_payload = logs_response.json()
    assert logs_payload['total'] == 1
    assert logs_payload['items'][0]['status'] == 'dry_run'
    assert logs_payload['items'][0]['channel_type'] == 'dingtalk_group'
    assert logs_payload['items'][0]['channel_key_masked'].startswith('chat')
    assert 'secret-001' not in logs_payload['items'][0]['channel_key_masked']


def test_agent_management_outbox_dispatch_redacts_secret_text_detail(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)

    def fake_dispatch(_db, outbox_message_id):
        return agent_communication_service.DispatchOutcome(
            status='retrying',
            detail='send failed password=detail-pass token=detail-token',
            outbox_message_id=int(outbox_message_id),
        )

    monkeypatch.setattr(agent_communication_service, 'dispatch_outbox_message', fake_dispatch)

    client = _client(session_factory, _user('admin'))
    try:
        response = client.post('/api/v1/agent-management/outbox/99/dispatch')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        'outbox_message_id': 99,
        'status': 'retrying',
        'detail': 'send failed password=<redacted> token=<redacted>',
    }


def test_agent_management_logs_include_provider_response_payload(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    db = session_factory()
    try:
        agent_communication_service.register_agent(db, code='factory_dispatch', name='全厂总控 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-prod-secret-002',
            name='测试总控群',
            target_type='management',
            target_key='management',
            dry_run=False,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-002',
        )
        message = agent_communication_service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-002',
            title='测试消息',
            content='真实发送模拟消息。',
            source_summary='unit_test',
            trace_id='trace-router-provider-response',
        )
        agent_communication_service.dispatch_outbox_message(
            db,
            message.id,
            sender=lambda _channel_key, _payload: (
                True,
                {
                    'detail': 'dingtalk_sent',
                    'provider_message_id': 'provider-msg-001',
                    'response_payload': {
                        'errcode': 0,
                        'access_token': 'should-not-leak',
                        'result': {'messageId': 'provider-msg-001'},
                    },
                },
            ),
        )
    finally:
        db.close()

    client = _client(session_factory, _user('admin'))
    try:
        response = client.get(f'/api/v1/agent-management/outbox/{message.id}/logs')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['items'][0]['provider_message_id'] == 'provider-msg-001'
    assert payload['items'][0]['response_payload'] == {
        'errcode': 0,
        'access_token': '***',
        'result': {'messageId': 'provider-msg-001'},
    }


def test_agent_management_logs_redact_nested_provider_secret_payload(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    db = session_factory()
    try:
        agent_communication_service.register_agent(db, code='factory_dispatch', name='全厂总控 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-prod-secret-003',
            name='测试总控群',
            target_type='management',
            target_key='management',
            dry_run=False,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-003',
        )
        message = agent_communication_service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-003',
            title='测试消息',
            content='真实发送模拟消息。',
            source_summary='unit_test',
            trace_id='trace-router-provider-nested-secret',
        )
        agent_communication_service.dispatch_outbox_message(
            db,
            message.id,
            sender=lambda _channel_key, _payload: (
                False,
                {
                    'detail': 'dingtalk_failed',
                    'provider_message_id': 'provider-msg-002',
                    'response_payload': {
                        'errcode': 310000,
                        'result': {
                            'request_id': 'req-provider-002',
                            'api_key': 'nested-api-key-should-not-leak',
                            'credential': 'nested-credential-should-not-leak',
                        },
                    },
                },
            ),
        )
    finally:
        db.close()

    client = _client(session_factory, _user('admin'))
    try:
        response = client.get(f'/api/v1/agent-management/outbox/{message.id}/logs')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['items'][0]['response_payload'] == {
        'errcode': 310000,
        'result': {
            'request_id': 'req-provider-002',
            'api_key': '***',
            'credential': '***',
        },
    }


def test_agent_management_logs_redact_secret_text_detail(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    db = session_factory()
    try:
        agent_communication_service.register_agent(db, code='factory_dispatch', name='全厂总控 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-prod-secret-004',
            name='测试总控群',
            target_type='management',
            target_key='management',
            dry_run=False,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-004',
        )
        message = agent_communication_service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-prod-secret-004',
            title='测试消息',
            content='真实发送模拟消息。',
            source_summary='unit_test',
            trace_id='trace-router-provider-detail-secret',
        )
        agent_communication_service.dispatch_outbox_message(
            db,
            message.id,
            sender=lambda _channel_key, _payload: (
                False,
                {
                    'detail': 'driver failed password=detail-pass token=detail-token',
                    'provider_message_id': 'provider-msg-003',
                    'response_payload': {'errcode': 310001},
                },
            ),
        )
    finally:
        db.close()

    client = _client(session_factory, _user('admin'))
    try:
        response = client.get(f'/api/v1/agent-management/outbox/{message.id}/logs')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    detail = response.json()['items'][0]['detail']
    assert 'detail-pass' not in detail
    assert 'detail-token' not in detail
    assert detail == 'driver failed password=<redacted> token=<redacted>'


def test_agent_management_outbox_dispatch_redacts_agent_error_detail(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)

    def fake_dispatch(_db, _outbox_message_id):
        raise agent_communication_service.AgentCommunicationError(
            'outbox lookup failed password=detail-pass token=detail-token'
        )

    monkeypatch.setattr(agent_communication_service, 'dispatch_outbox_message', fake_dispatch)

    client = _client(session_factory, _user('admin'))
    try:
        response = client.post('/api/v1/agent-management/outbox/99/dispatch')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    detail = response.json()['detail']
    assert 'detail-pass' not in detail
    assert 'detail-token' not in detail
    assert detail == 'outbox lookup failed password=<redacted> token=<redacted>'


def test_agent_management_can_dispatch_due_outbox_messages_with_redacted_details(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    calls = []

    def fake_dispatch_due(_db, *, limit=50):
        calls.append(limit)
        return [
            agent_communication_service.DispatchOutcome(
                status='sent',
                detail='dingtalk_sent',
                outbox_message_id=11,
            ),
            agent_communication_service.DispatchOutcome(
                status='retrying',
                detail='send failed authorization:detail-auth',
                outbox_message_id=12,
            ),
        ]

    monkeypatch.setattr(agent_communication_service, 'dispatch_due_outbox_messages', fake_dispatch_due)

    client = _client(session_factory, _user('admin'))
    try:
        response = client.post('/api/v1/agent-management/outbox/dispatch-due?limit=2')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [2]
    payload = response.json()
    assert payload == {
        'total': 2,
        'items': [
            {'outbox_message_id': 11, 'status': 'sent', 'detail': 'dingtalk_sent'},
            {
                'outbox_message_id': 12,
                'status': 'retrying',
                'detail': 'send failed authorization=<redacted>',
            },
        ],
    }


def test_agent_management_due_outbox_dispatch_rejects_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.post('/api/v1/agent-management/outbox/dispatch-due')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()['detail'] == 'Agent management access denied'


def test_agent_management_can_run_dry_run_smoke_without_real_send(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('admin'))
    try:
        response = client.post('/api/v1/agent-management/outbox/dry-run-smoke')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'dry_run'
    assert payload['detail'] == 'dry-run only, message not sent'
    assert payload['log_total'] == 1
    assert payload['outbox_message_id'] > 0
    assert payload['channel']['dry_run'] is True
    assert payload['channel']['channel_type'] == 'dingtalk_group'
    assert 'channel_key' not in payload['channel']
    assert payload['channel']['channel_key_masked']


def test_agent_management_dry_run_smoke_rejects_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.post('/api/v1/agent-management/outbox/dry-run-smoke')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()['detail'] == 'Agent management access denied'


def test_agent_management_outbox_dispatch_rejects_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.post('/api/v1/agent-management/outbox/1/dispatch')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()['detail'] == 'Agent management access denied'
