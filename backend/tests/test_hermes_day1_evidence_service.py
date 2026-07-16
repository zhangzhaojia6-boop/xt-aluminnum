from __future__ import annotations

from datetime import date
import hashlib
from importlib import import_module
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import MultimodalEvidence
from app.services.hermes_dingtalk_evidence_service import query_dingtalk_evidence


def _day1_service():
    return import_module('app.services.hermes_day1_evidence_service')


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_classify_dingtalk_evidence_covers_fact_explanation_instruction_and_noise() -> None:
    service = _day1_service()

    fact = service.classify_dingtalk_evidence('今日日报：冷轧产量 32 吨')
    explanation = service.classify_dingtalk_evidence('热轧停机，原因是设备故障')
    instruction = service.classify_dingtalk_evidence('日报产量按这个附件补录，以这个为准')
    generic_file = service.classify_dingtalk_evidence('', file_name='7月5日抄表.xlsx')
    noise = service.classify_dingtalk_evidence('收到，谢谢')

    assert fact.evidence_kind == 'fact'
    assert fact.evidence_grade == 'high'
    assert fact.include_in_daily_sample is True
    assert {'日报', '产量'}.issubset(set(fact.matched_keywords))

    assert explanation.evidence_kind == 'explanation'
    assert explanation.evidence_grade == 'medium'
    assert explanation.include_in_daily_sample is True
    assert {'停机', '原因', '故障'}.issubset(set(explanation.matched_keywords))

    assert instruction.evidence_kind == 'instruction'
    assert instruction.evidence_grade == 'high'
    assert instruction.include_in_daily_sample is True
    assert {'日报', '产量', '补录', '以这个为准'}.issubset(set(instruction.matched_keywords))

    assert generic_file.evidence_kind == 'fact'
    assert generic_file.evidence_grade == 'medium'
    assert generic_file.include_in_daily_sample is True

    assert noise.evidence_kind == 'noise'
    assert noise.evidence_grade == 'low'
    assert noise.include_in_daily_sample is False
    assert noise.matched_keywords == []


def test_record_day1_dingtalk_evidence_records_text_fact_payload() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={'msgtype': 'text', 'business_date_status': 'payload_explicit'},
            actor=SimpleNamespace(id=23),
            business_date=date(2026, 6, 21),
            channel='group_chat',
            group_id='group-001',
            trace_id='trace-001',
            recognized_text='今日日报：产量 32 吨',
        )

        assert evidence is not None
        assert evidence.id is not None
        assert evidence.evidence_type == 'text'
        assert evidence.file_uri is None
        assert evidence.source_user_id == 23
        assert evidence.recognized_text == '今日日报：产量 32 吨'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['source'] == 'dingtalk'
        assert evidence.payload['day1_super_brain'] is True
        assert evidence.payload['channel'] == 'group_chat'
        assert evidence.payload['group_id'] == 'group-001'
        assert evidence.payload['trace_id'] == 'trace-001'
        assert evidence.payload['business_date'] == '2026-06-21'
        assert evidence.payload['business_date_status'] == 'payload_explicit'
        assert evidence.payload['file_name'] is None
        assert evidence.payload['file_hash'] is None
        assert evidence.payload['parse_status'] == 'text_captured'
        assert evidence.payload['evidence_kind'] == 'fact'
        assert evidence.payload['evidence_grade'] == 'high'
        assert evidence.payload['include_in_daily_sample'] is True
        assert {'日报', '产量'}.issubset(set(evidence.payload['matched_keywords']))
        assert evidence.payload['metric_write_allowed'] is False
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        db.close()


def test_recorded_workshop_flows_into_unified_business_time_reader() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={
                'workshopName': '铸轧二车间',
                'eventTime': '2026-06-03T09:00:00+08:00',
                'parse_status': 'text_captured',
            },
            actor=None,
            business_date=None,
            channel='dingtalk_group',
            group_id='group-001',
            trace_id='trace-workshop-ingress',
            recognized_text='今日总产量 61 吨',
            confirmation_status='confirmed',
        )

        items = query_dingtalk_evidence(db, business_date=date(2026, 6, 2))

        assert evidence.payload['workshop_name'] == '铸二'
        assert len(items) == 1
        assert items[0].workshop_name == '铸二'
        assert items[0].business_date == date(2026, 6, 2)
        assert items[0].adoptable_as_fact is True
    finally:
        db.close()


def test_record_day1_dingtalk_evidence_records_attachment_hash_without_raw_file_id() -> None:
    service = _day1_service()
    db = _db_session()
    raw_file_id = 'media-raw-001'
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={
                'fileName': '每日产量.xlsx',
                'mediaId': raw_file_id,
                'fileId': 'secondary-file-id',
                'file_id': 'third-file-id',
            },
            actor=None,
            business_date=None,
            channel='dingtalk_group',
            group_id=None,
            trace_id='trace-file-001',
            recognized_text='',
        )

        assert evidence is not None
        assert evidence.evidence_type == 'attachment'
        assert evidence.file_uri == f'dingtalk://media/{raw_file_id}'
        assert evidence.source_user_id is None
        assert evidence.payload['file_name'] == '每日产量.xlsx'
        assert evidence.payload['file_hash'] == hashlib.sha1(raw_file_id.encode('utf-8')).hexdigest()
        assert evidence.payload['business_date'] is None
        assert evidence.payload['evidence_kind'] == 'fact'
        assert 'mediaId' not in evidence.payload
        assert 'fileId' not in evidence.payload
        assert 'file_id' not in evidence.payload
        assert raw_file_id not in str(evidence.payload)
    finally:
        db.close()


def test_record_day1_dingtalk_attachment_without_text_marks_text_unavailable() -> None:
    service = _day1_service()
    db = _db_session()
    raw_file_id = 'media-raw-empty-text'
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={
                'fileName': '每日产量.xlsx',
                'mediaId': raw_file_id,
            },
            actor=None,
            business_date=None,
            channel='dingtalk_group',
            group_id=None,
            trace_id='trace-file-no-text',
            recognized_text='   ',
        )

        assert evidence is not None
        assert evidence.evidence_type == 'attachment'
        assert evidence.payload['parse_status'] == 'text_unavailable'
        assert evidence.payload['evidence_kind'] == 'fact'
    finally:
        db.close()


def test_record_day1_dingtalk_file_name_without_media_id_still_records_trace() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={'fileName': '每日产量.xlsx'},
            actor=None,
            business_date=None,
            channel='dingtalk_group',
            group_id=None,
            trace_id='trace-file-missing-media',
            recognized_text='日报产量 32 吨',
        )

        assert evidence is not None
        assert evidence.file_uri is None
        assert evidence.payload['file_name'] == '每日产量.xlsx'
        assert evidence.payload['file_hash'] is None
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        db.close()


def test_record_day1_dingtalk_attachment_keeps_full_file_text_for_fact_parser() -> None:
    service = _day1_service()
    db = _db_session()
    long_report_text = (
        '2026年7月7日鑫泰铝业日报\n'
        '全厂总产量 416.47 吨\n'
        '成品入库 416.47 吨\n'
        '在制 1647.5 吨\n'
        '高压总用电 8440 度\n'
        '成品率 85.44%\n'
        + '补充说明' * 30
    )
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={'fileName': '2026年7月7日生产日报.txt', 'mediaId': 'media-full-text-001'},
            actor=None,
            business_date=date(2026, 7, 7),
            channel='dingtalk_group',
            group_id='group-001',
            trace_id='trace-file-full-text',
            recognized_text=long_report_text,
        )

        assert evidence is not None
        assert evidence.evidence_type == 'attachment'
        assert evidence.recognized_text.endswith('...')
        assert evidence.payload['recognized_text_truncated'] is True
        assert evidence.payload['file_text'] == long_report_text
        assert 'message_text' not in evidence.payload
    finally:
        db.close()


def test_record_day1_dingtalk_text_keeps_full_message_text_for_flexible_parser() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={'msgtype': 'text'},
            actor=SimpleNamespace(id=23),
            business_date=date(2026, 7, 7),
            channel='dingtalk_group',
            group_id='group-001',
            trace_id='trace-message-full-text',
            recognized_text='老板口径：7月7日总产量 416.47 吨，成品入库 416.47 吨',
        )

        assert evidence is not None
        assert evidence.evidence_type == 'text'
        assert evidence.payload['message_text'] == '老板口径：7月7日总产量 416.47 吨，成品入库 416.47 吨'
        assert 'file_text' not in evidence.payload
    finally:
        db.close()


def test_record_day1_dingtalk_evidence_stores_audit_metadata_and_filters_sensitive_keys() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={
                'senderStaffId': 'staff-001',
                'senderUnionId': 'union-001',
                'receivedAt': '2026-06-21T08:30:00+08:00',
                'messageTime': '2026-06-21T08:29:59+08:00',
                'password': 'plain-password',
                'token': 'plain-token',
                'cookie': 'plain-cookie',
            },
            actor=SimpleNamespace(id=23),
            business_date=date(2026, 6, 21),
            channel='group_chat',
            group_id='group-001',
            trace_id='trace-audit-001',
            recognized_text='日报产量 32 吨',
        )

        assert evidence is not None
        assert evidence.payload['dingtalk_sender_id'] == 'staff-001'
        assert evidence.payload['dingtalk_sender_union_id'] == 'union-001'
        assert evidence.payload['dingtalk_received_at'] == '2026-06-21T08:30:00+08:00'
        assert evidence.payload['dingtalk_message_time'] == '2026-06-21T08:29:59+08:00'
        assert 'password' not in evidence.payload
        assert 'token' not in evidence.payload
        assert 'cookie' not in evidence.payload
        assert 'plain-password' not in str(evidence.payload)
        assert 'plain-token' not in str(evidence.payload)
        assert 'plain-cookie' not in str(evidence.payload)
    finally:
        db.close()


def test_record_day1_dingtalk_evidence_keeps_noise_as_non_sample_trace() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={'msgtype': 'text'},
            actor=SimpleNamespace(id=23),
            business_date=date(2026, 6, 21),
            channel='group_chat',
            group_id='group-001',
            trace_id='trace-noise-001',
            recognized_text='收到，谢谢',
        )

        assert evidence is not None
        assert evidence.payload['evidence_kind'] == 'noise'
        assert evidence.payload['include_in_daily_sample'] is False
        assert evidence.payload['metric_write_allowed'] is False
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        db.close()


def test_record_day1_dingtalk_evidence_drops_sensitive_input_payload_keys() -> None:
    service = _day1_service()
    db = _db_session()
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={
                'file_name': '日报.txt',
                'mediaId': 'media-secret-001',
                'password': 'plain-password',
                'token': 'plain-token',
                'cookie': 'plain-cookie',
            },
            actor=SimpleNamespace(id=23),
            business_date=date(2026, 6, 21),
            channel='group_chat',
            group_id='group-001',
            trace_id='trace-secret-001',
            recognized_text='日报产量 32 吨',
        )

        assert evidence is not None
        assert 'password' not in evidence.payload
        assert 'token' not in evidence.payload
        assert 'cookie' not in evidence.payload
        assert 'plain-password' not in str(evidence.payload)
        assert 'plain-token' not in str(evidence.payload)
        assert 'plain-cookie' not in str(evidence.payload)
    finally:
        db.close()


def test_record_day1_dingtalk_evidence_stores_safe_snippet_for_long_sensitive_text() -> None:
    service = _day1_service()
    db = _db_session()
    unique_tail_marker = 'UNIQUE-MARKER-SHOULD-NOT-SURVIVE'
    recognized_text = (
        '今日日报：产量 32 吨；password=plain-password；token=plain-token；'
        + ('前半段说明' * 40)
        + unique_tail_marker
    )
    try:
        evidence = service.record_day1_dingtalk_evidence(
            db,
            payload={'msgtype': 'text'},
            actor=SimpleNamespace(id=23),
            business_date=date(2026, 6, 21),
            channel='group_chat',
            group_id='group-001',
            trace_id='trace-long-sensitive-001',
            recognized_text=recognized_text,
        )

        assert evidence is not None
        assert evidence.recognized_text != recognized_text
        assert len(evidence.recognized_text) <= 123
        assert unique_tail_marker not in evidence.recognized_text
        assert 'plain-password' not in evidence.recognized_text
        assert 'plain-token' not in evidence.recognized_text
        assert 'plain-password' not in str(evidence.payload)
        assert 'plain-token' not in str(evidence.payload)
        assert evidence.payload['recognized_text_hash'] == hashlib.sha1(recognized_text.encode('utf-8')).hexdigest()
        assert evidence.payload['recognized_text_chars'] == len(recognized_text)
        assert evidence.payload['recognized_text_truncated'] is True
    finally:
        db.close()
