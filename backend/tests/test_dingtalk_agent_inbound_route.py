from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.database import get_db
from app.main import app
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentOutboxMessage,
    AgentProfile,
    AgentRateLimit,
    AgentRun,
    ChatInboxMessage,
    CommunicationChannel,
    DingTalkInboundReceipt,
    MultimodalEvidence,
)
from app.models.energy import EnergyImportRecord
from app.models.imports import ImportBatch, ImportRow
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.reports import DailyReport
from app.models.system import User
from app.routers import dingtalk as dingtalk_router
from app.services import dingtalk_service
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
    AgentRateLimit.__table__,
    ChatInboxMessage.__table__,
    DingTalkInboundReceipt.__table__,
    AgentRun.__table__,
    MultimodalEvidence.__table__,
    ImportBatch.__table__,
    ImportRow.__table__,
    EnergyImportRecord.__table__,
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


def test_chat_inbox_allows_only_one_row_per_inbound_receipt() -> None:
    db, previous_overrides = _install_db_override()
    receipt = DingTalkInboundReceipt(
        dedupe_key='a' * 64,
        channel='dingtalk_group',
        group_id='cid-concurrent-dedupe',
        trace_id='trace-concurrent-dedupe-001',
    )
    db.add(receipt)
    db.commit()

    def build_inbox() -> ChatInboxMessage:
        return ChatInboxMessage(
            channel='dingtalk_group',
            group_id='cid-concurrent-dedupe',
            sender_external_id='dt-concurrent-001',
            text='并发回调证据',
            agent_code='factory_dispatch',
            trace_id='trace-concurrent-dedupe-001',
            inbound_dedupe_key=receipt.dedupe_key,
        )

    try:
        db.add(build_inbox())
        db.commit()

        db.add(build_inbox())
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        _restore_db_override(previous_overrides, db)


def _restore_db_override(previous_overrides, db: Session) -> None:
    db.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def _write_dingtalk_energy_workbook(path: Path) -> None:
    frame = pd.DataFrame(
        [
            ['7月份各车间电耗统计表', '', '', '', ''],
            ['车间/日期', '1日', '2日', '3日', '4日'],
            ['铸锭', 100, 200, 300, 400],
            ['热轧', 10, 20, 30, 40],
        ]
    )
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, header=False, sheet_name='用量')


def test_dingtalk_inbound_receipt_dedupe_key_is_database_unique() -> None:
    db, previous_overrides = _install_db_override()
    try:
        db.add(
            DingTalkInboundReceipt(
                dedupe_key='a' * 64,
                channel='dingtalk_group',
                group_id='cid-unique-001',
                trace_id='trace-unique-001',
            )
        )
        db.commit()
        db.add(
            DingTalkInboundReceipt(
                dedupe_key='a' * 64,
                channel='dingtalk_group',
                group_id='cid-unique-001',
                trace_id='trace-unique-001',
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        _restore_db_override(previous_overrides, db)


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
        assert payload['energy_ingest']['status'] == 'skipped'
        assert payload['energy_ingest']['reason'] == 'no_inline_file_content'
        inbox = db.query(ChatInboxMessage).one()
        assert payload['chat_inbox_id'] == inbox.id
        assert payload['agent_run_id'] is None
        assert inbox.trace_id == 'trace-dingtalk-file-only-001'
        assert inbox.text == '7月5日抄表.xlsx'
        assert inbox.source_payload['parse_status'] == 'download_failed'
        assert inbox.source_payload['download_status'] == 'missing_download_code'
        assert inbox.source_payload['downloadCode_present'] is False
        assert inbox.source_payload['business_date_status'] == 'missing'
        assert 'business_date' in inbox.source_payload
        assert inbox.source_payload['business_date'] is None
        assert db.query(AgentRun).count() == 0
        assert db.query(EnergyImportRecord).count() == 0

        evidence = db.query(MultimodalEvidence).one()
        assert payload['evidence_id'] == evidence.id
        assert evidence.evidence_type == 'attachment'
        assert evidence.file_uri == 'dingtalk://media/media-energy-20260705'
        assert evidence.payload['channel'] == 'dingtalk_group'
        assert evidence.payload['group_id'] == 'cid-energy-files'
        assert evidence.payload['source_transport'] == 'dingtalk_signed_inbound'
        assert evidence.payload['file_name'] == '7月5日抄表.xlsx'
        assert evidence.payload['evidence_kind'] == 'fact'
        assert evidence.payload['metric_write_allowed'] is False
        assert evidence.payload['business_date'] is None
        assert evidence.payload['business_date_status'] == 'missing'
        assert evidence.payload['energy_ingest']['status'] == 'skipped'
        assert datetime.fromisoformat(evidence.payload['dingtalk_received_at']).tzinfo is not None
        assert inbox.source_payload['receivedAt'] == evidence.payload['dingtalk_received_at']
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_stages_inline_energy_workbook_without_promoting(monkeypatch, tmp_path: Path) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=13,
            username='energy-inline-manager',
            password_hash='x',
            name='能耗负责人',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-energy-inline-001',
            dingtalk_union_id='union-energy-inline-001',
        )
    )
    db.commit()

    workbook = tmp_path / '7月份各车间电耗统计表.xlsx'
    _write_dingtalk_energy_workbook(workbook)
    encoded = base64.b64encode(workbook.read_bytes()).decode('ascii')

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.services.dingtalk_energy_ingest_service.settings.UPLOAD_DIR',
        str(tmp_path / 'uploads'),
        raising=False,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-energy-files',
                'conversationType': 'group',
                'senderStaffId': 'dt-energy-inline-001',
                'senderUnionId': 'union-energy-inline-001',
                'msgtype': 'file',
                'fileName': '7月份各车间电耗统计表.xlsx',
                'mediaId': 'media-energy-20260704',
                'fileContentBase64': encoded,
                'business_date': '2026-07-04',
                'traceId': 'trace-dingtalk-inline-energy-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['action'] == 'dingtalk-evidence-recorded'
        assert payload['energy_ingest']['status'] == 'staged'
        assert payload['energy_ingest']['business_date'] == '2026-07-04'
        assert payload['energy_ingest']['batch_id']

        assert db.query(EnergyImportRecord).count() == 0
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['business_date'] == '2026-07-04'
        assert evidence.payload['energy_ingest']['status'] == 'staged'
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_downloads_top_level_file_secret_without_persisting_it(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=113,
            username='energy-downloader-top-level',
            password_hash='x',
            name='能耗负责人',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-energy-download-top-001',
            dingtalk_union_id='union-energy-download-top-001',
        )
    )
    db.commit()
    calls: list[str] = []

    def _fake_download_robot_message_file(*, download_code: str):
        calls.append(download_code)
        return dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content='日期,产量\n2026-07-07,32\n'.encode('utf-8'),
            content_type='text/csv',
            size=24,
        )

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.dingtalk_service.service.download_robot_message_file',
        _fake_download_robot_message_file,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-energy-download-top',
                'conversationType': 'group',
                'senderStaffId': 'dt-energy-download-top-001',
                'senderUnionId': 'union-energy-download-top-001',
                'msgtype': 'file',
                'fileName': '7月7日产量.csv',
                'fileId': 'file-top-001',
                'downloadCode': 'download-top-secret-001',
                'messageTime': '2026-07-07T08:31:02+08:00',
                'receivedAt': '2026-07-07T08:31:05+08:00',
                'traceId': 'trace-dingtalk-file-download-top-001',
            },
        )

        assert response.status_code == 200
        assert calls == ['download-top-secret-001']
        evidence = db.query(MultimodalEvidence).one()
        flattened = str(evidence.payload)
        assert evidence.payload['file_text'] == '日期\t产量\n2026-07-07\t32'
        assert evidence.payload['dingtalk_message_time'] == '2026-07-07T08:31:02+08:00'
        assert evidence.payload['dingtalk_received_at'] == '2026-07-07T08:31:05+08:00'
        assert evidence.payload['download_status'] == 'downloaded'
        assert evidence.payload['downloadCode_present'] is True
        assert 'download-top-secret-001' not in flattened
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_uses_nested_download_secret_but_keeps_storage_clean(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=114,
            username='energy-downloader-nested',
            password_hash='x',
            name='能耗负责人',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-energy-download-nested-001',
            dingtalk_union_id='union-energy-download-nested-001',
        )
    )
    db.commit()
    calls: list[str] = []
    signed_url = (
        'https://files.dingtalk.com/download/report.xlsx'
        '?access_token=token-raw-001&signature=signature-raw-001'
        '&downloadCode=download-nested-secret-001&expires=1720681200'
    )

    def _fake_download_robot_message_file(*, download_code: str):
        calls.append(download_code)
        return dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content='日期,产量\n2026-07-08,18\n'.encode('utf-8'),
            content_type='text/csv',
            size=24,
        )

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.dingtalk_service.service.download_robot_message_file',
        _fake_download_robot_message_file,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-energy-download-nested',
                'conversationType': 'group',
                'senderStaffId': 'dt-energy-download-nested-001',
                'senderUnionId': 'union-energy-download-nested-001',
                'msgtype': 'file',
                'fileName': '7月8日产量.csv',
                'fileId': 'file-nested-001',
                'content': json.dumps(
                    {
                        'downloadCode': 'download-nested-secret-001',
                        'signedUrl': signed_url,
                    },
                    ensure_ascii=False,
                ),
                'traceId': 'trace-dingtalk-file-download-nested-001',
            },
        )

        assert response.status_code == 200
        assert calls == ['download-nested-secret-001']
        evidence = db.query(MultimodalEvidence).one()
        flattened = str(evidence.payload)
        assert evidence.payload['download_status'] == 'downloaded'
        for secret in (
            'download-nested-secret-001',
            'token-raw-001',
            'signature-raw-001',
            signed_url,
        ):
            assert secret not in flattened
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


def test_dingtalk_agent_inbound_keeps_out_of_scope_file_as_candidate_without_running_agent(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add_all([
        User(
            id=201,
            username='cold_director_file_denied',
            password_hash='x',
            name='冷轧主任',
            role='workshop_director',
            is_manager=True,
            is_reviewer=True,
            workshop_id=20,
            is_active=True,
            dingtalk_user_id='dt-cold-director-file-denied-001',
            dingtalk_union_id='union-cold-director-file-denied-001',
        ),
        Workshop(id=10, code='RZ', name='热轧', workshop_type='hot_roll', sort_order=1, is_active=True),
        Workshop(id=20, code='LZ2050', name='冷轧2050', workshop_type='cold_roll', sort_order=2, is_active=True),
        CommunicationChannel(
            channel_type='dingtalk_group',
            channel_key='cid-hot-roll-file',
            name='热轧附件群',
            target_type='workshop',
            target_key='热轧',
            workshop_id=10,
            dry_run=True,
            is_active=True,
        ),
    ])
    db.commit()
    download_calls: list[str] = []

    def _fake_download_robot_message_file(*, download_code: str):
        download_calls.append(download_code)
        raise RuntimeError('download unavailable')

    stream_secret = 'stream-relay-test-secret'
    monkeypatch.setattr('app.routers.dingtalk.settings.APP_ENV', 'production', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.settings.HERMES_DINGTALK_STREAM_RELAY_TOKEN',
        stream_secret,
        raising=False,
    )
    monkeypatch.setattr(
        'app.routers.dingtalk.dingtalk_service.service.download_robot_message_file',
        _fake_download_robot_message_file,
    )

    try:
        client = TestClient(app)
        inbound_payload = {
            'conversationId': 'cid-hot-roll-file',
            'conversationType': 'group',
            'senderStaffId': 'dt-cold-director-file-denied-001',
            'senderUnionId': 'union-cold-director-file-denied-001',
            'msgtype': 'file',
            'fileName': '7月9日产量.csv',
            'fileId': 'file-scope-denied-001',
            'downloadCode': 'download-scope-denied-001',
            'traceId': 'trace-dingtalk-file-scope-denied-001',
        }
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers=_signed_inbound_headers(inbound_payload, stream_secret, kind='dingtalk_stream'),
            json=inbound_payload,
        )

        assert response.status_code == 200
        assert response.json()['should_reply'] is False
        assert download_calls == ['download-scope-denied-001']
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['parse_status'] == 'download_failed'
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
                'createTime': '2026-06-20T08:30:00+08:00',
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
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.trace_id == 'trace-dingtalk-day1-disabled-001'
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
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.trace_id == 'trace-dingtalk-redacted-error-001'
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
                'createTime': '2026-06-20T08:30:00+08:00',
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
            'business_date': '2026-06-19',
            'actor_id': 13,
            'chat_inbox_id': payload['chat_inbox_id'],
        }
        assert db.query(MultimodalEvidence).count() == 1
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
                'createTime': '2026-06-20T08:30:00+08:00',
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-day1-non-owner-001',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'owner_required'
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.trace_id == 'trace-dingtalk-day1-non-owner-001'
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
                'createTime': '2025-06-20T08:30:00+08:00',
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-day1-fact-403-001',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'owner_required'
        assert db.query(MultimodalEvidence).count() == 1
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['business_date'] == '2025-06-19'
        assert evidence.payload['business_date_status'] == 'command_explicit'
        assert evidence.payload['evidence_kind'] == 'fact'
        assert db.query(DailyReport).count() == 0
        assert db.query(AgentRun).count() == 0
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.trace_id == 'trace-dingtalk-day1-fact-403-001'
        assert inbox.source_payload['business_date'] == '2025-06-19'
        assert inbox.source_payload['business_date_status'] == 'command_explicit'
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
        'createTime': '2026-06-20T08:30:00+08:00',
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
        assert second.status_code == 200
        assert first.json()['detail'] == 'owner_required'
        assert second.json()['action'] == 'dingtalk-duplicate'
        assert db.query(MultimodalEvidence).count() == 1
        assert db.query(ChatInboxMessage).count() == 1
        assert db.query(DingTalkInboundReceipt).count() == 1
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
        'createTime': '2026-06-20T08:30:00+08:00',
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
        assert second.json()['action'] == 'dingtalk-duplicate'
        assert db.query(MultimodalEvidence).count() == 1
        assert db.query(ChatInboxMessage).count() == 1
        assert db.query(DingTalkInboundReceipt).count() == 1
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
        assert evidence.confirmation_status == 'machine_only'
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
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['evidence_kind'] == 'noise'
        assert evidence.payload['include_in_daily_sample'] is False
        assert evidence.payload['metric_write_allowed'] is False
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_ignores_payload_outbox_override_without_bound_channel(monkeypatch) -> None:
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
                'queueOutbox': 'true',
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


def test_dingtalk_agent_inbound_duplicate_file_callback_downloads_once(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=202,
            username='manager-dedupe-file-download',
            password_hash='x',
            name='生产经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-dedupe-file-download-001',
            dingtalk_union_id='union-manager-dedupe-file-download-001',
        )
    )
    db.commit()
    download_calls: list[str] = []

    def _fake_download_robot_message_file(*, download_code: str):
        download_calls.append(download_code)
        return dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content='日期,产量\n2026-07-09,32\n'.encode('utf-8'),
            content_type='text/csv',
            size=24,
        )

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.dingtalk_service.service.download_robot_message_file',
        _fake_download_robot_message_file,
    )

    payload = {
        'conversationId': 'cid-dedupe-file-download-test',
        'conversationType': 'group',
        'senderStaffId': 'dt-manager-dedupe-file-download-001',
        'senderUnionId': 'union-manager-dedupe-file-download-001',
        'msgtype': 'file',
        'fileName': '7月9日产量.csv',
        'fileId': 'file-dedupe-download-001',
        'downloadCode': 'download-dedupe-secret-001',
        'traceId': 'trace-dingtalk-file-download-dedupe-001',
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
        assert first.json()['action'] == 'dingtalk-evidence-recorded'
        assert second.json()['action'] == 'dingtalk-duplicate'
        assert download_calls == ['download-dedupe-secret-001']
        assert db.query(MultimodalEvidence).count() == 1
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.source_payload['parse_status'] == 'text_captured'
        assert inbox.source_payload['download_status'] == 'downloaded'
        assert inbox.source_payload['downloadCode_present'] is True
        assert len(inbox.source_payload['file_hash']) == 64
        assert 'download-dedupe-secret-001' not in str(inbox.source_payload)
        assert db.query(DingTalkInboundReceipt).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_sanitizes_chat_inbox_source_payload_download_secrets(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=194,
            username='root-owner-secret-sanitize',
            password_hash='x',
            name='root_owner',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root-secret-sanitize-001',
            dingtalk_union_id='union-root-secret-sanitize-001',
        )
    )
    db.commit()
    signed_url = (
        'https://files.dingtalk.com/download/report.xlsx'
        '?access_token=token-chat-001&signature=signature-chat-001'
        '&downloadCode=download-chat-001&expires=1720681200'
    )

    monkeypatch.setattr('app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN', 'inbound-test', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DAY1_ENABLED', True, raising=False)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root-secret-sanitize-001')
    monkeypatch.setattr(
        'app.routers.dingtalk.run_day1_super_brain',
        lambda *_args, **_kwargs: type(
            'FakeDay1Result',
            (),
            {
                'trace_id': 'trace-dingtalk-chat-secret-001',
                'status': 'generated',
                'answer': '日报已生成',
                'reply_messages': ['日报已生成'],
                'agent_run_id': 1,
                'report_id': 1,
            },
        )(),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'inbound-test'},
            json={
                'conversationId': 'cid-chat-secret-sanitize',
                'conversationType': '1',
                'senderStaffId': 'dt-root-secret-sanitize-001',
                'senderUnionId': 'union-root-secret-sanitize-001',
                'text': {'content': '生成 6月19日正式日报'},
                'createTime': '2026-06-20T08:30:00+08:00',
                'msgParam': json.dumps(
                    {
                        'downloadCode': 'download-chat-001',
                        'nested': {'signedUrl': signed_url},
                    },
                    ensure_ascii=False,
                ),
                'signedUrl': signed_url,
                'traceId': 'trace-dingtalk-chat-secret-001',
                'queueOutbox': 'false',
            },
        )

        assert response.status_code == 200
        inbox = db.get(ChatInboxMessage, response.json()['chat_inbox_id'])
        assert inbox is not None
        flattened = str(inbox.source_payload)
        for secret in (
            'download-chat-001',
            'token-chat-001',
            'signature-chat-001',
            signed_url,
        ):
            assert secret not in flattened
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
        assert seen["mes_reader"] is not None
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


def _signed_inbound_headers(
    payload: dict,
    secret: str,
    *,
    timestamp: int | None = None,
    kind: str = 'signed_inbound',
    nonce: str = 'test-nonce-001',
) -> dict[str, str]:
    request_time = int(time.time()) if timestamp is None else timestamp
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    signed = (
        str(request_time).encode('ascii')
        + b'.'
        + nonce.encode('ascii')
        + b'.'
        + kind.encode('ascii')
        + b'.'
        + canonical
    )
    signature = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    return {
        'x-dingtalk-inbound-timestamp': str(request_time),
        'x-dingtalk-inbound-nonce': nonce,
        'x-dingtalk-inbound-kind': kind,
        'x-dingtalk-inbound-signature': f'sha256={signature}',
    }


def test_production_inbound_signature_accepts_unknown_metadata_and_rejects_tampering(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    secret = 'stream-relay-test-secret'
    payload = {
        'conversationId': 'cid-unknown-event-001',
        'conversationType': 'group',
        'senderStaffId': 'unbound-staff-001',
        'msgtype': 'custom_unknown',
        'traceId': 'trace-unknown-event-001',
        'rawNote': '未知事件也必须留元数据',
    }
    monkeypatch.setattr(dingtalk_router.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'DINGTALK_INBOUND_TOKEN', 'generic-secret', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DINGTALK_INBOUND_TOKEN', '', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DINGTALK_STREAM_RELAY_TOKEN', secret, raising=False)

    try:
        client = TestClient(app)
        accepted = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers=_signed_inbound_headers(payload, secret, kind='dingtalk_stream'),
            json=payload,
        )
        tampered_payload = {**payload, 'rawNote': '被篡改'}
        tampered = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers=_signed_inbound_headers(payload, secret, kind='dingtalk_stream'),
            json=tampered_payload,
        )

        assert accepted.status_code == 200
        accepted_payload = accepted.json()
        assert accepted_payload['should_reply'] is False
        receipt = db.query(DingTalkInboundReceipt).one()
        inbox = db.query(ChatInboxMessage).one()
        evidence = db.query(MultimodalEvidence).one()
        assert receipt.trace_id == 'trace-unknown-event-001'
        assert accepted_payload['chat_inbox_id'] == inbox.id
        assert inbox.trace_id == receipt.trace_id
        assert inbox.text == 'custom_unknown'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['trace_id'] == receipt.trace_id
        assert evidence.payload['source_transport'] == 'dingtalk_stream'
        assert evidence.payload['raw_metadata']['rawNote'] == '未知事件也必须留元数据'
        assert tampered.status_code == 401
        assert tampered.json()['detail'] == 'dingtalk_inbound_signature_invalid'
    finally:
        _restore_db_override(previous_overrides, db)


def test_production_inbound_signature_rejects_expired_timestamp(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    secret = 'signed-inbound-test-secret'
    payload = {'traceId': 'trace-expired-001', 'msgtype': 'custom_unknown'}
    monkeypatch.setattr(dingtalk_router.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'DINGTALK_INBOUND_TOKEN', secret, raising=False)

    try:
        response = TestClient(app).post(
            '/api/v1/dingtalk/agent-inbound',
            headers=_signed_inbound_headers(payload, secret, timestamp=int(time.time()) - 301),
            json=payload,
        )

        assert response.status_code == 401
        assert response.json()['detail'] == 'dingtalk_inbound_timestamp_expired'
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_production_inbound_signature_rejects_exact_nonce_replay(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    secret = 'stream-replay-test-secret'
    payload = {
        'traceId': 'trace-replay-001',
        'msgtype': 'custom_unknown',
        'rawNote': '仅首次可接收',
    }
    headers = _signed_inbound_headers(
        payload,
        secret,
        kind='dingtalk_stream',
        nonce='nonce-replay-001',
    )
    monkeypatch.setattr(dingtalk_router.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_DINGTALK_STREAM_RELAY_TOKEN', secret, raising=False)

    try:
        client = TestClient(app)
        first = client.post('/api/v1/dingtalk/agent-inbound', headers=headers, json=payload)
        replay = client.post('/api/v1/dingtalk/agent-inbound', headers=headers, json=payload)

        assert first.status_code == 200
        assert replay.status_code == 409
        assert replay.json()['detail'] == 'dingtalk_inbound_replay_detected'
        assert db.query(AgentRateLimit).count() == 1
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_generic_inbound_secret_cannot_claim_stream_transport(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    generic_secret = 'generic-inbound-secret'
    payload = {'traceId': 'trace-fake-stream-001', 'msgtype': 'custom_unknown'}
    monkeypatch.setattr(dingtalk_router.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'DINGTALK_INBOUND_TOKEN', generic_secret, raising=False)
    monkeypatch.setattr(
        dingtalk_router.settings,
        'HERMES_DINGTALK_STREAM_RELAY_TOKEN',
        'different-stream-secret',
        raising=False,
    )

    try:
        response = TestClient(app).post(
            '/api/v1/dingtalk/agent-inbound',
            headers=_signed_inbound_headers(payload, generic_secret, kind='dingtalk_stream'),
            json=payload,
        )

        assert response.status_code == 401
        assert response.json()['detail'] == 'dingtalk_inbound_signature_invalid'
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_unprivileged_bound_user_message_is_retained_without_agent_side_effects(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=999,
            username='operator-candidate-only',
            password_hash='x',
            name='一线员工',
            role='operator',
            is_active=True,
            dingtalk_user_id='dt-operator-candidate-001',
        )
    )
    db.commit()
    stream_secret = 'stream-relay-operator-secret'
    monkeypatch.setattr(dingtalk_router.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(
        dingtalk_router.settings,
        'HERMES_DINGTALK_STREAM_RELAY_TOKEN',
        stream_secret,
        raising=False,
    )

    try:
        inbound_payload = {
            'senderStaffId': 'dt-operator-candidate-001',
            'text': {'content': '本班出现一卷表面划伤，先留证'},
            'traceId': 'trace-operator-candidate-001',
        }
        response = TestClient(app).post(
            '/api/v1/dingtalk/agent-inbound',
            headers=_signed_inbound_headers(inbound_payload, stream_secret, kind='dingtalk_stream'),
            json=inbound_payload,
        )

        assert response.status_code == 200
        assert response.json()['should_reply'] is False
        assert db.query(MultimodalEvidence).count() == 1
        inbox = db.query(ChatInboxMessage).one()
        assert response.json()['chat_inbox_id'] == inbox.id
        assert inbox.trace_id == 'trace-operator-candidate-001'
        assert db.query(AgentRun).count() == 0
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        _restore_db_override(previous_overrides, db)


def test_failed_agent_processing_can_retry_without_duplicate_evidence(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=1001,
            username='retry-manager',
            password_hash='x',
            name='重试管理员',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-retry-manager-001',
        )
    )
    db.commit()
    monkeypatch.setattr(dingtalk_router.settings, 'DINGTALK_INBOUND_TOKEN', 'retry-secret', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_FACTORY_BRAIN_ENABLED', False, raising=False)
    calls = 0

    def flaky_handle(*_args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('temporary agent failure')
        return type(
            'RetryResult',
            (),
            {
                'trace_id': kwargs['trace_id'],
                'status_color': 'green',
                'intent': 'help',
                'answer': '重试后已恢复',
                'chat_inbox_id': 2001,
                'agent_run_id': 2002,
                'outbox_message_id': None,
            },
        )()

    monkeypatch.setattr(dingtalk_router, 'handle_agent_command', flaky_handle)
    inbound_payload = {
        'senderStaffId': 'dt-retry-manager-001',
        'text': {'content': '/commands'},
        'traceId': 'trace-agent-retry-001',
    }

    try:
        client = TestClient(app, raise_server_exceptions=False)
        first = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'retry-secret'},
            json=inbound_payload,
        )
        second = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'retry-secret'},
            json=inbound_payload,
        )

        assert first.status_code == 500
        assert second.status_code == 200
        assert second.json()['answer'] == '重试后已恢复'
        assert calls == 2
        assert db.query(MultimodalEvidence).count() == 1
        receipt = db.query(DingTalkInboundReceipt).one()
        assert receipt.status == 'completed'
        assert receipt.attempt_count == 2
    finally:
        _restore_db_override(previous_overrides, db)


def _install_processing_recovery_fixture(db: Session, monkeypatch, *, status: str, updated_at: datetime):
    db.add(
        User(
            id=1002,
            username='processing-recovery-manager',
            password_hash='x',
            name='恢复管理员',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-processing-recovery-001',
        )
    )
    db.commit()
    monkeypatch.setattr(dingtalk_router.settings, 'DINGTALK_INBOUND_TOKEN', 'recovery-secret', raising=False)
    monkeypatch.setattr(dingtalk_router.settings, 'HERMES_FACTORY_BRAIN_ENABLED', False, raising=False)
    payload = {
        'senderStaffId': 'dt-processing-recovery-001',
        'text': {'content': '/commands'},
        'traceId': 'trace-processing-recovery-001',
    }
    receipt, created = dingtalk_router._claim_inbound_receipt(
        db,
        channel='dingtalk_private',
        group_id='',
        trace_id=payload['traceId'],
        source_transport='dingtalk_signed_inbound',
    )
    assert created is True
    dingtalk_router.ingest_dingtalk_stream_event(
        db,
        payload,
        require_authorized_group=False,
        source_transport='dingtalk_signed_inbound',
    )
    receipt.status = status
    receipt.attempt_count = 1
    receipt.updated_at = updated_at
    db.commit()
    return payload, receipt


def test_evidence_pending_receipt_recovers_from_committed_evidence(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    calls = 0

    def recovered_handle(*_args, **kwargs):
        nonlocal calls
        calls += 1
        return type(
            'RecoveryResult',
            (),
            {
                'trace_id': kwargs['trace_id'],
                'status_color': 'green',
                'intent': 'help',
                'answer': '证据恢复后继续处理',
                'chat_inbox_id': 3001,
                'agent_run_id': 3002,
                'outbox_message_id': None,
            },
        )()

    try:
        payload, _receipt = _install_processing_recovery_fixture(
            db,
            monkeypatch,
            status='evidence_pending',
            updated_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(dingtalk_router, 'handle_agent_command', recovered_handle)

        response = TestClient(app).post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'recovery-secret'},
            json=payload,
        )

        assert response.status_code == 200
        assert response.json()['answer'] == '证据恢复后继续处理'
        assert calls == 1
        receipt = db.query(DingTalkInboundReceipt).one()
        assert receipt.status == 'completed'
        assert receipt.attempt_count == 2
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        _restore_db_override(previous_overrides, db)


def test_stale_agent_processing_receipt_can_be_reclaimed(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    calls = 0

    def recovered_handle(*_args, **kwargs):
        nonlocal calls
        calls += 1
        return type(
            'RecoveryResult',
            (),
            {
                'trace_id': kwargs['trace_id'],
                'status_color': 'green',
                'intent': 'help',
                'answer': '超时任务已接管',
                'chat_inbox_id': 3003,
                'agent_run_id': 3004,
                'outbox_message_id': None,
            },
        )()

    try:
        payload, _receipt = _install_processing_recovery_fixture(
            db,
            monkeypatch,
            status='agent_processing',
            updated_at=datetime.now(timezone.utc)
            - timedelta(seconds=dingtalk_router.INBOUND_AGENT_PROCESSING_LEASE_SECONDS + 1),
        )
        monkeypatch.setattr(dingtalk_router, 'handle_agent_command', recovered_handle)

        response = TestClient(app).post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'recovery-secret'},
            json=payload,
        )

        assert response.status_code == 200
        assert response.json()['answer'] == '超时任务已接管'
        assert calls == 1
        receipt = db.query(DingTalkInboundReceipt).one()
        assert receipt.status == 'completed'
        assert receipt.attempt_count == 2
    finally:
        _restore_db_override(previous_overrides, db)


def test_fresh_agent_processing_receipt_returns_retryable_error(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    try:
        payload, _receipt = _install_processing_recovery_fixture(
            db,
            monkeypatch,
            status='agent_processing',
            updated_at=datetime.now(timezone.utc),
        )

        response = TestClient(app).post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'recovery-secret'},
            json=payload,
        )

        assert response.status_code == 503
        assert response.json()['detail'] == 'dingtalk_inbound_agent_processing'
        receipt = db.query(DingTalkInboundReceipt).one()
        assert receipt.status == 'agent_processing'
        assert receipt.attempt_count == 1
    finally:
        _restore_db_override(previous_overrides, db)
