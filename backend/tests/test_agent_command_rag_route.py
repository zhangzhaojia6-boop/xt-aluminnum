from __future__ import annotations

from datetime import date, time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentOutboxMessage,
    AgentProfile,
    AgentRun,
    ChatInboxMessage,
    CommunicationChannel,
)
from app.models.consumable import DailyConsumableLog
from app.models.master import Equipment, Workshop
from app.models.production import ShiftProductionData
from app.models.quality import DataQualityIssue, QualityIssueLog
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.shift import ShiftConfig
from app.models.system import User
from app.routers import agent as agent_router
from app.services import agent_communication_service
from app.services.agent_command_service import AgentCommandError
from app.services.rag_service import create_document_from_bytes


AGENT_COMMAND_TABLES = [
    User.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    Workshop.__table__,
    Equipment.__table__,
    ShiftConfig.__table__,
    ShiftProductionData.__table__,
    DataQualityIssue.__table__,
    QualityIssueLog.__table__,
    DailyConsumableLog.__table__,
    AgentProfile.__table__,
    CommunicationChannel.__table__,
    AgentChannelBinding.__table__,
    AgentOutboxMessage.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
]


def _install_overrides(*, role: str = 'admin', user_kwargs: dict | None = None):
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=AGENT_COMMAND_TABLES)
    db = Session(engine)

    def fake_get_db():
        yield db

    def fake_get_user() -> User:
        return User(
            id=1,
            username=role,
            password_hash='x',
            name='User',
            role=role,
            is_active=True,
            **(user_kwargs or {}),
        )

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    return db, previous_overrides


def _restore_overrides(previous_overrides, db: Session) -> None:
    db.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_agent_command_answers_from_rag_and_records_audit_trail() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='换辊处理规则.md',
            content=('换辊超时需要通知设备员，超过三十分钟升级为橙色异常。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        db.commit()

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-test',
                'sender_external_id': 'ding-user-001',
                'text': '换辊超时怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-rag-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['trace_id'] == 'trace-agent-rag-001'
        assert payload['status_color'] == 'green'
        assert payload['answer'].startswith('【全厂｜')
        assert '状态：绿' in payload['answer']
        assert '换辊超时' in payload['answer']
        assert '数据来源' in payload['answer']
        assert payload['rag']['citations'][0]['filename'] == '换辊处理规则.md'
        assert payload['outbox_message_id'] is None

        inbox = db.query(ChatInboxMessage).one()
        assert inbox.group_id == 'chat-test'
        assert inbox.sender_external_id == 'ding-user-001'
        assert inbox.text == '换辊超时怎么办'
        assert inbox.trace_id == 'trace-agent-rag-001'

        run = db.query(AgentRun).one()
        assert run.trace_id == 'trace-agent-rag-001'
        assert run.agent_code == 'maintenance_agent'
        assert run.rag_citation_count == 1
        assert run.status == 'answered'
        assert run.result_payload['status_color'] == 'green'

        assert db.query(RagQueryLog).count() == 1
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_filters_rag_by_workshop_and_machine_code() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='冷轧换辊标准.md',
            content=('换辊标准要求先停机挂牌，确认张力后通知维修。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
            source_name='冷轧换辊标准',
            metadata={'workshop': '冷轧2050', 'machine_code': 'LZ2050-9'},
        )
        create_document_from_bytes(
            db,
            filename='热轧1号机换辊标准.md',
            content=('换辊标准要求先停机挂牌，确认轧辊温度后通知维修。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
            source_name='热轧1号机换辊标准',
            metadata={'workshop': '热轧', 'machine_code': 'RZ-1'},
        )
        db.commit()

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-012',
                'text': '换辊标准怎么做',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-rag-scope-001',
                'workshop': '热轧',
                'machine_code': 'RZ-1',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['rag']['citations']
        assert payload['rag']['citations'][0]['filename'] == '热轧1号机换辊标准.md'
        assert payload['rag']['citations'][0]['metadata']['workshop'] == '热轧'
        assert payload['rag']['citations'][0]['metadata']['machine_code'] == 'RZ-1'
        assert '冷轧换辊标准.md' not in payload['answer']

        query_log = db.query(RagQueryLog).one()
        assert query_log.result_count == 1
        assert query_log.citations[0]['filename'] == '热轧1号机换辊标准.md'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_requires_management_scope() -> None:
    db, previous_overrides = _install_overrides(role='machine_operator')

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-test',
                'sender_external_id': 'ding-user-001',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'Agent command access denied'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_rejects_outbox_channel_outside_user_workshop() -> None:
    db, previous_overrides = _install_overrides(
        role='workshop_director',
        user_kwargs={'workshop_id': 20, 'is_manager': True, 'is_reviewer': True},
    )

    try:
        db.add_all([
            Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
            Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        ])
        db.commit()
        agent_communication_service.register_agent(db, code='maintenance_agent', name='修停机 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-hot-roll',
            name='热轧状态群',
            target_type='workshop',
            target_key='热轧',
            workshop_id=10,
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='maintenance_agent',
            channel_key='chat-hot-roll',
            channel_type='dingtalk_group',
        )

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-hot-roll',
                'sender_external_id': 'internal-cold-director',
                'text': '点检标准怎么做',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-command-denied-001',
                'queue_outbox': True,
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'Agent command channel scope denied'
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_rejects_requested_workshop_outside_user_scope() -> None:
    db, previous_overrides = _install_overrides(
        role='workshop_director',
        user_kwargs={'workshop_id': 20, 'is_manager': True, 'is_reviewer': True},
    )

    try:
        db.add_all([
            Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
            Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        ])
        db.commit()

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'internal',
                'sender_external_id': 'internal-cold-director',
                'text': '点检标准怎么做',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-workshop-denied-001',
                'workshop': '热轧',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'Agent command workshop scope denied'
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_redacts_agent_error_detail(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()

    def fake_handle_agent_command(*_args, **_kwargs):
        raise AgentCommandError('agent failed password=detail-pass token=detail-token')

    monkeypatch.setattr(agent_router, 'handle_agent_command', fake_handle_agent_command)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-test',
                'sender_external_id': 'ding-user-001',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
            },
        )

        assert response.status_code == 400
        detail = response.json()['detail']
        assert 'detail-pass' not in detail
        assert 'detail-token' not in detail
        assert detail == 'agent failed password=<redacted> token=<redacted>'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_filters_sensitive_source_payload_before_audit_storage() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-test',
                'sender_external_id': 'ding-user-001',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
                'trace_id': 'trace-source-payload-redaction',
                'source_payload': {
                    'message_id': 'msg-001',
                    'access_token': 'source-token-should-not-store',
                    'sender': {
                        'name': '张三',
                        'password': 'nested-password-should-not-store',
                    },
                    'items': [
                        {'event_id': 'evt-001', 'api_key': 'nested-api-key-should-not-store'},
                    ],
                },
            },
        )

        assert response.status_code == 200
        inbox = db.query(ChatInboxMessage).one()
        run = db.query(AgentRun).one()
        assert inbox.source_payload == {
            'message_id': 'msg-001',
            'sender': {'name': '张三'},
            'items': [{'event_id': 'evt-001'}],
        }
        assert run.result_payload['source_payload'] == inbox.source_payload
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_detects_business_intent_without_fabricating_numbers() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-management',
                'sender_external_id': 'ding-user-004',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
                'trace_id': 'trace-agent-intent-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'production_today'
        assert payload['status_color'] == 'yellow'
        assert '无新增生产数字' in payload['answer']

        run = db.query(AgentRun).one()
        assert run.result_payload['intent'] == 'production_today'
        assert run.result_payload['fact_status'] == 'not_connected'
        assert db.query(ChatInboxMessage).one().text == '今日产量'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_uses_live_production_fact_for_today_output(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()

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
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-management',
                'sender_external_id': 'ding-user-005',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
                'trace_id': 'trace-agent-fact-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'production_today'
        assert payload['status_color'] == 'green'
        assert '包装产量 42.50 吨' in payload['answer']
        assert '全厂入库产量 39.25 吨' in payload['answer']
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['business_date'] == '2026-06-09'

        run = db.query(AgentRun).one()
        assert run.result_payload['fact_status'] == 'connected'
        assert run.result_payload['facts']['daily_output_tons'] == 42.5
        assert run.result_payload['facts']['finished_inbound_output_tons'] == 39.25
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_uses_live_anomaly_fact_for_workshop_summary(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'overall_progress': {
                'pending_assignment': {
                    'entry_count': 3,
                    'workshop_count': 2,
                    'rows': [
                        {
                            'workshop_name': '冷轧2050',
                            'entry_count': 2,
                            'missing_machine_count': 2,
                            'missing_shift_count': 0,
                        },
                        {
                            'workshop_name': '拉矫',
                            'entry_count': 1,
                            'missing_machine_count': 0,
                            'missing_shift_count': 1,
                        },
                    ],
                },
            },
            'data_quality': {
                'missing_output_weight': {
                    'entry_count': 1,
                    'items': [
                        {
                            'workshop_name': '冷轧2050',
                            'machine_name': '2050#主操',
                            'tracking_card_no': 'RA260609001',
                        },
                    ],
                },
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

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
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-management',
                'sender_external_id': 'ding-user-006',
                'text': '哪个车间异常',
                'agent_code': 'factory_dispatch',
                'trace_id': 'trace-agent-anomaly-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'anomaly_summary'
        assert payload['status_color'] == 'orange'
        assert '冷轧2050' in payload['answer']
        assert '未匹配机列/班次 3 条' in payload['answer']
        assert '缺下机量 1 条' in payload['answer']
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['anomaly_count'] == 4

        run = db.query(AgentRun).one()
        assert run.result_payload['fact_status'] == 'connected'
        assert run.result_payload['facts']['top_workshops'][0] == '冷轧2050'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_uses_consumable_targets_for_over_quota_summary(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()
    db.add_all([
        Workshop(id=2, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=1, is_active=True),
        Workshop(id=3, code='LJ', name='拉矫', workshop_type='straightening', sort_order=2, is_active=True),
        DailyConsumableLog(
            workshop_id=2,
            workshop_type='cold_roll',
            business_date=date(2026, 6, 9),
            payload={
                'hydraulic_oil_daily': 12,
                'hydraulic_oil_target': 10,
                'gear_oil_daily': 8,
                'gear_oil_target': 10,
                'rolling_oil_per_ton': 1.8,
            },
        ),
        DailyConsumableLog(
            workshop_id=3,
            workshop_type='straightening',
            business_date=date(2026, 6, 9),
            payload={
                'hydraulic_oil_daily': 5,
                'hydraulic_oil_target': 6,
            },
        ),
    ])
    db.commit()

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-management',
                'sender_external_id': 'ding-user-007',
                'text': '辅材是否超耗',
                'agent_code': 'consumable_agent',
                'trace_id': 'trace-agent-consumable-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'consumable_usage'
        assert payload['status_color'] == 'orange'
        assert '冷轧2050' in payload['answer']
        assert '液压油' in payload['answer']
        assert '超耗 1 项' in payload['answer']
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['over_quota_count'] == 1
        assert payload['facts']['unchecked_value_count'] == 1

        run = db.query(AgentRun).one()
        assert run.result_payload['fact_status'] == 'connected'
        assert run.result_payload['facts']['top_over_quota'][0]['workshop_name'] == '冷轧2050'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_consumable_facts_stay_within_user_workshop(monkeypatch) -> None:
    db, previous_overrides = _install_overrides(
        role='workshop_director',
        user_kwargs={'workshop_id': 20, 'is_manager': True, 'is_reviewer': True},
    )
    db.add_all([
        Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
        Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        DailyConsumableLog(
            workshop_id=10,
            workshop_type='hot_roll',
            business_date=date(2026, 6, 9),
            payload={
                'hydraulic_oil_daily': 24,
                'hydraulic_oil_target': 10,
            },
        ),
        DailyConsumableLog(
            workshop_id=20,
            workshop_type='cold_roll',
            business_date=date(2026, 6, 9),
            payload={
                'hydraulic_oil_daily': 5,
                'hydraulic_oil_target': 10,
            },
        ),
    ])
    db.commit()

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'internal',
                'sender_external_id': 'cold-director',
                'text': '辅材是否超耗',
                'agent_code': 'consumable_agent',
                'trace_id': 'trace-agent-consumable-scope-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'consumable_usage'
        assert payload['status_color'] == 'green'
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['log_count'] == 1
        assert payload['facts']['over_quota_count'] == 0
        assert payload['facts']['top_over_quota'] == []
        assert '热轧' not in payload['answer']

        run = db.query(AgentRun).one()
        assert run.result_payload['facts']['log_count'] == 1
        assert run.result_payload['facts']['over_quota_count'] == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_uses_shift_downtime_fact_for_machine_stop(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()
    db.add_all([
        Workshop(id=4, code='RZ', name='热轧车间', workshop_type='hot_roll', sort_order=1, is_active=True),
        Equipment(id=21, code='RZ-2', name='2号机', workshop_id=4, operational_status='stopped', is_active=True),
        Equipment(id=22, code='RZ-1', name='1号机', workshop_id=4, operational_status='running', is_active=True),
        ShiftConfig(
            id=31,
            code='DAY',
            name='长白班',
            shift_type='day',
            start_time=time(7, 30),
            end_time=time(15, 30),
            is_active=True,
        ),
        ShiftProductionData(
            business_date=date(2026, 6, 9),
            shift_config_id=31,
            workshop_id=4,
            equipment_id=21,
            downtime_minutes=42,
            downtime_reason='换辊待维修确认',
            output_weight=12.5,
            data_status='submitted',
            data_source='mobile_shift_report',
        ),
        ShiftProductionData(
            business_date=date(2026, 6, 9),
            shift_config_id=31,
            workshop_id=4,
            equipment_id=22,
            downtime_minutes=0,
            output_weight=18.5,
            data_status='submitted',
            data_source='mobile_shift_report',
        ),
    ])
    db.commit()

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-008',
                'text': '2号机为什么停',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-stop-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'machine_stop'
        assert payload['status_color'] == 'orange'
        assert '2号机' in payload['answer']
        assert '42 分钟' in payload['answer']
        assert '换辊待维修确认' in payload['answer']
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['machine_filter'] == '2'
        assert payload['facts']['top_stops'][0]['downtime_minutes'] == 42

        run = db.query(AgentRun).one()
        assert run.result_payload['fact_status'] == 'connected'
        assert run.result_payload['facts']['top_stops'][0]['equipment_name'] == '2号机'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_machine_stop_facts_stay_within_user_workshop(monkeypatch) -> None:
    db, previous_overrides = _install_overrides(
        role='workshop_director',
        user_kwargs={'workshop_id': 20, 'is_manager': True, 'is_reviewer': True},
    )
    db.add_all([
        Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
        Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        Equipment(id=21, code='RZ-2', name='2号机', workshop_id=10, operational_status='stopped', is_active=True),
        ShiftConfig(
            id=31,
            code='DAY',
            name='长白班',
            shift_type='day',
            start_time=time(7, 30),
            end_time=time(15, 30),
            is_active=True,
        ),
        ShiftProductionData(
            business_date=date(2026, 6, 9),
            shift_config_id=31,
            workshop_id=10,
            equipment_id=21,
            downtime_minutes=42,
            downtime_reason='热轧换辊待维修确认',
            output_weight=12.5,
            data_status='submitted',
            data_source='mobile_shift_report',
        ),
    ])
    db.commit()

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'internal',
                'sender_external_id': 'cold-director',
                'text': '2号机为什么停',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-stop-scope-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'machine_stop'
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['stop_count'] == 0
        assert payload['facts']['top_stops'] == []
        assert '热轧' not in payload['answer']
        assert '热轧换辊待维修确认' not in payload['answer']

        run = db.query(AgentRun).one()
        assert run.result_payload['facts']['stop_count'] == 0
        assert run.result_payload['facts']['top_stops'] == []
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_uses_quality_gate_and_issue_facts(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()
    db.add_all([
        Workshop(id=5, code='LZ1850', name='冷轧1850', workshop_type='cold_roll', sort_order=1, is_active=True),
        DataQualityIssue(
            business_date=date(2026, 6, 9),
            issue_type='quality_gate',
            source_type='yield_matrix',
            dimension_key='workshop:LZ1850',
            field_name='yield_rate',
            issue_level='blocker',
            issue_desc='质量门禁阻断：冷轧1850成品率低于红线',
            status='open',
        ),
        DataQualityIssue(
            business_date=date(2026, 6, 9),
            issue_type='missing_data',
            source_type='energy',
            dimension_key='energy',
            field_name='energy_value',
            issue_level='warning',
            issue_desc='当日未导入能耗数据',
            status='open',
        ),
        QualityIssueLog(
            business_date=date(2026, 6, 9),
            workshop_id=5,
            tracking_card_no='RA260609009',
            quality_issue_type='surface',
            quality_issue_desc='表面划伤复核',
        ),
    ])
    db.commit()

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-quality',
                'sender_external_id': 'ding-user-009',
                'text': '质量门禁有没有异常',
                'agent_code': 'quality_agent',
                'trace_id': 'trace-agent-quality-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'quality_anomaly'
        assert payload['status_color'] == 'red'
        assert '质量门禁阻断' in payload['answer']
        assert '现场质量问题 1 条' in payload['answer']
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['blocker_count'] == 1
        assert payload['facts']['quality_issue_count'] == 1

        run = db.query(AgentRun).one()
        assert run.result_payload['fact_status'] == 'connected'
        assert run.result_payload['facts']['top_blockers'][0]['issue_desc'] == '质量门禁阻断：冷轧1850成品率低于红线'
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_quality_facts_stay_within_user_workshop(monkeypatch) -> None:
    db, previous_overrides = _install_overrides(
        role='workshop_director',
        user_kwargs={'workshop_id': 20, 'is_manager': True, 'is_reviewer': True},
    )
    db.add_all([
        Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
        Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        DataQualityIssue(
            business_date=date(2026, 6, 9),
            issue_type='quality_gate',
            source_type='yield_matrix',
            dimension_key='workshop:RZ',
            field_name='yield_rate',
            issue_level='blocker',
            issue_desc='热轧质量门禁阻断：成品率低于红线',
            status='open',
        ),
        QualityIssueLog(
            business_date=date(2026, 6, 9),
            workshop_id=10,
            tracking_card_no='RZ260609009',
            quality_issue_type='surface',
            quality_issue_desc='热轧表面划伤复核',
        ),
    ])
    db.commit()

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'internal',
                'sender_external_id': 'cold-director',
                'text': '质量门禁有没有异常',
                'agent_code': 'quality_agent',
                'trace_id': 'trace-agent-quality-scope-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'quality_anomaly'
        assert payload['status_color'] == 'green'
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['blocker_count'] == 0
        assert payload['facts']['quality_issue_count'] == 0
        assert payload['facts']['top_blockers'] == []
        assert payload['facts']['top_quality_issues'] == []
        assert '热轧' not in payload['answer']

        run = db.query(AgentRun).one()
        assert run.result_payload['facts']['blocker_count'] == 0
        assert run.result_payload['facts']['quality_issue_count'] == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_uses_energy_summary_fact_for_energy_cost(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()

    def fake_energy_summary(*_args, **_kwargs):
        return {
            'electricity_value': 131500.0,
            'gas_value': 53433.0,
            'water_value': 0.0,
            'total_energy': 184933.0,
            'total_output_weight': 343.481,
            'output_basis': 'mes_packaging_output',
            'energy_per_ton': 538.4,
            'primary_source': 'mobile_shift_report',
            'mobile_totals': {'row_count': 3, 'total_energy': 184933.0},
            'owner_totals': {'row_count': 1, 'total_energy': 180000.0},
            'system_totals': {'row_count': 0, 'total_energy': 0.0},
        }

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.energy_service.summarize_energy_for_date',
        fake_energy_summary,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-energy',
                'sender_external_id': 'ding-user-010',
                'text': '今日能耗成本怎么样',
                'agent_code': 'energy_cost_agent',
                'trace_id': 'trace-agent-energy-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'energy_cost'
        assert payload['status_color'] == 'green'
        assert '电量 131500.00 度' in payload['answer']
        assert '气量 53433.00 立方' in payload['answer']
        assert '吨耗 538.40' in payload['answer']
        assert '成本金额暂无' in payload['answer']
        assert payload['facts']['status'] == 'connected'
        assert payload['facts']['primary_source'] == 'mobile_shift_report'
        assert payload['facts']['output_basis'] == 'mes_packaging_output'

        run = db.query(AgentRun).one()
        assert run.result_payload['fact_status'] == 'connected'
        assert run.result_payload['facts']['energy_per_ton'] == 538.4
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_energy_facts_stay_within_user_workshop(monkeypatch) -> None:
    db, previous_overrides = _install_overrides(
        role='workshop_director',
        user_kwargs={'workshop_id': 20, 'is_manager': True, 'is_reviewer': True},
    )
    scoped_workshop_ids: list[int | None] = []

    def fake_energy_summary(_db, *, business_date, workshop_id=None):
        scoped_workshop_ids.append(workshop_id)
        if workshop_id == 20:
            return {
                'electricity_value': 1200.0,
                'gas_value': 300.0,
                'water_value': 0.0,
                'total_energy': 1500.0,
                'total_output_weight': 12.0,
                'output_basis': 'energy_rows',
                'energy_per_ton': 125.0,
                'primary_source': 'mobile_shift_report',
                'mobile_totals': {'row_count': 1, 'total_energy': 1500.0},
                'owner_totals': {'row_count': 0, 'total_energy': 0.0},
                'system_totals': {'row_count': 0, 'total_energy': 0.0},
            }
        return {
            'electricity_value': 131500.0,
            'gas_value': 53433.0,
            'water_value': 0.0,
            'total_energy': 184933.0,
            'total_output_weight': 343.481,
            'output_basis': 'mes_packaging_output',
            'energy_per_ton': 538.4,
            'primary_source': 'mobile_shift_report',
            'mobile_totals': {'row_count': 3, 'total_energy': 184933.0},
            'owner_totals': {'row_count': 1, 'total_energy': 180000.0},
            'system_totals': {'row_count': 0, 'total_energy': 0.0},
        }

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.energy_service.summarize_energy_for_date',
        fake_energy_summary,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'internal',
                'sender_external_id': 'cold-director',
                'text': '今日能耗成本怎么样',
                'agent_code': 'energy_cost_agent',
                'trace_id': 'trace-agent-energy-scope-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['intent'] == 'energy_cost'
        assert scoped_workshop_ids == [20]
        assert '电量 1200.00 度' in payload['answer']
        assert '吨耗 125.00' in payload['answer']
        assert '131500.00' not in payload['answer']
        assert payload['facts']['electricity_kwh'] == 1200.0
        assert payload['facts']['energy_per_ton'] == 125.0

        run = db.query(AgentRun).one()
        assert run.result_payload['facts']['electricity_kwh'] == 1200.0
        assert run.result_payload['facts']['energy_per_ton'] == 125.0
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_can_queue_bound_group_reply_without_dispatch() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='停机升级规则.md',
            content=('停机超过三十分钟需要升级给车间负责人，并进入橙色状态。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        agent_communication_service.register_agent(db, code='maintenance_agent', name='修停机 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-maintenance',
            name='修停机测试群',
            target_type='workshop',
            target_key='maintenance',
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='maintenance_agent',
            channel_key='chat-maintenance',
        )

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-002',
                'text': '停机超过三十分钟怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-outbox-001',
                'queue_outbox': True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['outbox_message_id'] is not None

        message = db.get(AgentOutboxMessage, payload['outbox_message_id'])
        assert message is not None
        assert message.status == 'pending'
        assert message.attempts == 0
        assert message.trace_id == 'trace-agent-outbox-001'
        assert message.content == payload['answer']
        assert message.payload['chat_inbox_id'] == payload['chat_inbox_id']
        assert message.payload['agent_run_id'] == payload['agent_run_id']
        assert message.payload['rag_citation_count'] == 1

        run = db.get(AgentRun, payload['agent_run_id'])
        assert run.result_payload['outbox_message_id'] == payload['outbox_message_id']
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_outbox_labels_business_fact_source(monkeypatch) -> None:
    db, previous_overrides = _install_overrides()

    def fake_live_aggregation(*_args, **_kwargs):
        return {
            'business_date': '2026-06-09',
            'factory_total': {
                'daily_output': 42.5,
                'finished_inbound_output': 39.25,
                'daily_output_source': 'mes_stock_records',
                'finished_inbound_source': 'storage_owner_daily_entry',
                'business_day_start': '07:30',
            },
            'mes_sync_status': {'status': 'ok'},
            'data_source': 'mixed',
        }

    monkeypatch.setattr(
        'app.services.agent_command_service.resolve_production_business_date',
        lambda: date(2026, 6, 9),
    )
    monkeypatch.setattr(
        'app.services.agent_command_service.realtime_service.build_live_aggregation',
        fake_live_aggregation,
    )

    try:
        agent_communication_service.register_agent(db, code='factory_dispatch', name='全厂总控 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-management',
            name='管理测试群',
            target_type='factory',
            target_key='factory',
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-management',
        )

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-management',
                'sender_external_id': 'ding-user-011',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
                'trace_id': 'trace-agent-fact-outbox-001',
                'queue_outbox': True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        message = db.get(AgentOutboxMessage, payload['outbox_message_id'])
        assert message is not None
        assert message.title == '【factory_dispatch】今日产量回复'
        assert message.source_summary == 'agent_command_production_today'
        assert message.payload['intent'] == 'production_today'
        assert message.payload['fact_status'] == 'connected'
        assert message.payload['rag_citation_count'] == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_reuses_group_reply_outbox_for_same_question() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='停机升级规则.md',
            content=('停机超过三十分钟需要升级给车间负责人，并进入橙色状态。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        agent_communication_service.register_agent(db, code='maintenance_agent', name='修停机 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-maintenance',
            name='修停机测试群',
            target_type='workshop',
            target_key='maintenance',
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='maintenance_agent',
            channel_key='chat-maintenance',
        )

        client = TestClient(app)
        first = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-002',
                'text': '停机超过三十分钟怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-outbox-101',
                'queue_outbox': True,
            },
        )
        second = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-003',
                'text': '停机超过三十分钟怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-outbox-102',
                'queue_outbox': True,
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        first_payload = first.json()
        second_payload = second.json()
        assert second_payload['outbox_message_id'] == first_payload['outbox_message_id']
        assert db.query(AgentOutboxMessage).count() == 1

        message = db.get(AgentOutboxMessage, first_payload['outbox_message_id'])
        assert message is not None
        assert message.dedupe_key == 'agent_command:dingtalk_group:chat-maintenance:maintenance_agent:8d8bd2d8b199e09b'
        assert message.dedupe_expires_at is not None
        assert db.query(ChatInboxMessage).count() == 2
        assert db.query(AgentRun).count() == 2
    finally:
        _restore_overrides(previous_overrides, db)
