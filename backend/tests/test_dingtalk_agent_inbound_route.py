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
    AgentRun,
    ChatInboxMessage,
)
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.system import User


DINGTALK_AGENT_TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
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
                'business_day_start': '07:30',
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
