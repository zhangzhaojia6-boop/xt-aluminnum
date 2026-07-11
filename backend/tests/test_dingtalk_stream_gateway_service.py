from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO
import json

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import MultimodalEvidence
from app.services import dingtalk_service
from app.services import dingtalk_stream_gateway_service as gateway


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _allow_group(monkeypatch, group_id: str = 'group-001') -> None:
    monkeypatch.setattr(gateway.settings, 'DINGTALK_AUTHORIZED_GROUP_IDS', group_id, raising=False)
    monkeypatch.setattr(gateway.settings, 'DINGTALK_FILE_TEXT_MAX_BYTES', 1_000_000, raising=False)


def _text_payload(**overrides):
    data = {
        'conversationId': 'group-001',
        'conversationType': 'group',
        'messageId': 'msg-001',
        'senderStaffId': 'staff-001',
        'senderUnionId': 'union-001',
        'msgtype': 'text',
        'text': {'content': '今日日报：产量 32 吨'},
        'businessDate': '2026-06-28',
        'createTime': '2026-06-28T08:30:00+08:00',
    }
    data.update(overrides)
    return {'data': data}


def _file_payload(**overrides):
    data = {
        'conversationId': 'group-001',
        'conversationType': 'group',
        'messageId': 'file-msg-001',
        'senderStaffId': 'staff-001',
        'senderUnionId': 'union-001',
        'msgtype': 'file',
        'content': {
            'fileName': '2026-07-07日报.csv',
            'downloadCode': 'download-code-001',
            'fileId': 'file-001',
        },
        'businessDate': '2026-07-07',
        'createTime': '2026-07-07T08:30:00+08:00',
    }
    data.update(overrides)
    return {'data': data}


class FakeDingTalkService:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    def download_robot_message_file(self, *, download_code: str):
        self.calls.append(download_code)
        if self.error is not None:
            raise self.error
        return self.result


def test_authorized_text_event_writes_message_text(monkeypatch) -> None:
    _allow_group(monkeypatch)
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(db, _text_payload())

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert result['duplicate'] is False
        assert result['message_text'] is True
        assert result['parse_status'] == 'text_captured'
        assert evidence.evidence_type == 'text'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['message_text'] == '今日日报：产量 32 吨'
        assert evidence.payload['business_date'] == '2026-06-28'
        assert evidence.payload['group_id'] == 'group-001'
        assert evidence.payload['trace_id'] == 'msg-001'
    finally:
        db.close()


def test_authorized_file_event_writes_file_text(monkeypatch) -> None:
    _allow_group(monkeypatch)
    content = '日期,产量\n2026-07-07,32\n'.encode()
    fake_dingtalk = FakeDingTalkService(
        result=dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content=content,
            content_type='text/csv',
            size=len(content),
        )
    )
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _file_payload(),
            dingtalk_service=fake_dingtalk,
        )

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert result['file_text'] is True
        assert result['parse_status'] == 'text_captured'
        assert fake_dingtalk.calls == ['download-code-001']
        assert evidence.evidence_type == 'attachment'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['file_text'] == '日期\t产量\n2026-07-07\t32'
        assert evidence.payload['file_hash'] == sha256(content).hexdigest()
        assert evidence.payload['downloadCode_present'] is True
        assert evidence.payload['download_status'] == 'downloaded'
        assert evidence.payload['download_url_host'] == 'files.dingtalk.com'
        assert 'download-code-001' not in str(evidence.payload)
    finally:
        db.close()


def test_unauthorized_event_writes_nothing(monkeypatch) -> None:
    _allow_group(monkeypatch, group_id='group-999')
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(db, _text_payload())

        assert result['accepted'] is False
        assert result['reason'] == 'unauthorized_group_id'
        assert '今日日报' not in str(result)
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        db.close()


def test_wildcard_group_scope_writes_message_from_any_group(monkeypatch) -> None:
    _allow_group(monkeypatch, group_id='*')
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _text_payload(conversationId='group-any-001', text={'content': '全量钉钉事实：入库 10 吨'}),
        )

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert evidence.payload['group_id'] == 'group-any-001'
        assert evidence.payload['message_text'] == '全量钉钉事实：入库 10 吨'
    finally:
        db.close()


def test_wildcard_scope_keeps_private_conversation_identifier(monkeypatch) -> None:
    _allow_group(monkeypatch, group_id='*')
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _text_payload(
                conversationId='cid-private-001',
                conversationType='private',
                text={'content': '这是私聊原话，也要留痕'},
            ),
        )

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert evidence.payload['channel'] == 'dingtalk_private'
        assert evidence.payload['group_id'] == 'cid-private-001'
        assert evidence.payload['message_text'] == '这是私聊原话，也要留痕'
    finally:
        db.close()


def test_duplicate_event_writes_once_and_does_not_redownload(monkeypatch) -> None:
    _allow_group(monkeypatch)
    content = b'field,value\noutput,32\n'
    fake_dingtalk = FakeDingTalkService(
        result=dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content=content,
            content_type='text/csv',
            size=len(content),
        )
    )
    db = _db_session()
    try:
        first = gateway.ingest_dingtalk_stream_event(db, _file_payload(), dingtalk_service=fake_dingtalk)
        second = gateway.ingest_dingtalk_stream_event(db, _file_payload(), dingtalk_service=fake_dingtalk)

        assert first['duplicate'] is False
        assert second['duplicate'] is True
        assert fake_dingtalk.calls == ['download-code-001']
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        db.close()


def test_download_failure_writes_metadata_only(monkeypatch) -> None:
    _allow_group(monkeypatch)
    fake_dingtalk = FakeDingTalkService(
        error=dingtalk_service.DingTalkFileDownloadError('signed url should not be stored')
    )
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _file_payload(),
            dingtalk_service=fake_dingtalk,
        )

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert result['file_text'] is False
        assert result['parse_status'] == 'download_failed'
        assert evidence.recognized_text is None
        assert evidence.payload['parse_status'] == 'download_failed'
        assert evidence.payload['download_status'] == 'download_failed'
        assert 'file_text' not in evidence.payload
        assert 'signed url' not in str(evidence.payload)
    finally:
        db.close()


def test_unsupported_file_type_writes_parse_status_without_fake_text(monkeypatch) -> None:
    _allow_group(monkeypatch)
    content = b'%PDF-1.4 fake'
    fake_dingtalk = FakeDingTalkService(
        result=dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content=content,
            content_type='application/pdf',
            size=len(content),
        )
    )
    db = _db_session()
    try:
        payload = _file_payload(content={'fileName': '日报.pdf', 'downloadCode': 'download-code-001', 'fileId': 'file-001'})
        result = gateway.ingest_dingtalk_stream_event(db, payload, dingtalk_service=fake_dingtalk)

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert result['file_text'] is False
        assert result['parse_status'] == 'unsupported_file_type'
        assert evidence.payload['parse_status'] == 'unsupported_file_type'
        assert 'file_text' not in evidence.payload
    finally:
        db.close()


def test_unknown_event_type_is_retained_as_metadata_only_evidence(monkeypatch) -> None:
    _allow_group(monkeypatch)
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _text_payload(
                messageId='msg-unknown-001',
                msgtype='unknown_event',
                text=None,
                content={'status': 'opaque'},
                rawNote='token=abc123',
            ),
        )

        evidence = db.query(MultimodalEvidence).one()
        assert result['accepted'] is True
        assert result['message_text'] is False
        assert result['file_text'] is False
        assert result['parse_status'] == 'text_unavailable'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.recognized_text is None
        assert evidence.payload['parse_status'] == 'text_unavailable'
        assert evidence.payload['messageType'] == 'unknown_event'
        assert evidence.payload['raw_metadata']['rawNote'] == 'token=<redacted>'
        assert evidence.payload['raw_metadata']['content']['status'] == 'opaque'
        assert 'message_text' not in evidence.payload
        assert 'file_text' not in evidence.payload
    finally:
        db.close()


def test_stringified_msg_param_metadata_redacts_embedded_download_secrets(monkeypatch) -> None:
    _allow_group(monkeypatch)
    signed_url = (
        'https://files.dingtalk.com/download/report.xlsx'
        '?access_token=token-raw-001&signature=signature-raw-001'
        '&downloadCode=download-raw-001&expires=1720681200'
    )
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _text_payload(
                messageId='msg-stringified-secret-001',
                text=None,
                msgParam=json.dumps(
                    {
                        'content': '字符串 JSON 里的原话要留，secret 不能留',
                        'downloadCode': 'download-secret-001',
                        'nested': {
                            'download_code': 'download-secret-002',
                            'signedUrl': signed_url,
                        },
                    },
                    ensure_ascii=False,
                ),
            ),
        )

        evidence = db.query(MultimodalEvidence).one()
        raw_metadata = evidence.payload['raw_metadata']
        flattened = str(raw_metadata)
        assert result['accepted'] is True
        assert result['message_text'] is True
        assert raw_metadata['msgParam']['content'] == '字符串 JSON 里的原话要留，secret 不能留'
        assert raw_metadata['msgParam']['nested']['signedUrl'].startswith(
            'https://files.dingtalk.com/download/report.xlsx?'
        )
        assert 'expires=1720681200' in raw_metadata['msgParam']['nested']['signedUrl']
        assert 'access_token=<redacted>' in raw_metadata['msgParam']['nested']['signedUrl']
        assert 'signature=<redacted>' in raw_metadata['msgParam']['nested']['signedUrl']
        assert 'downloadCode=<redacted>' in raw_metadata['msgParam']['nested']['signedUrl']
        for secret in (
            'download-secret-001',
            'download-secret-002',
            'token-raw-001',
            'signature-raw-001',
            'download-raw-001',
            signed_url,
        ):
            assert secret not in flattened
    finally:
        db.close()


def test_raw_metadata_redacts_signed_download_urls_inside_plain_strings(monkeypatch) -> None:
    _allow_group(monkeypatch)
    signed_url = (
        'https://files.dingtalk.com/download/report.xlsx'
        '?access_token=token-plain-001&signature=signature-plain-001'
        '&downloadCode=download-plain-001&expires=1720681200'
    )
    db = _db_session()
    try:
        gateway.ingest_dingtalk_stream_event(
            db,
            _text_payload(
                messageId='msg-plain-signed-url-001',
                text={'content': '明文 URL 也不能把签名带进库'},
                signedUrl=signed_url,
                rawLinks=[
                    signed_url,
                    {'previewUrl': signed_url, 'name': '日报附件'},
                ],
            ),
        )

        evidence = db.query(MultimodalEvidence).one()
        raw_metadata = evidence.payload['raw_metadata']
        flattened = str(raw_metadata)
        assert raw_metadata['signedUrl'].startswith('https://files.dingtalk.com/download/report.xlsx?')
        assert 'expires=1720681200' in raw_metadata['signedUrl']
        assert 'access_token=<redacted>' in raw_metadata['signedUrl']
        assert 'signature=<redacted>' in raw_metadata['signedUrl']
        assert 'downloadCode=<redacted>' in raw_metadata['signedUrl']
        assert raw_metadata['rawLinks'][1]['previewUrl'].startswith(
            'https://files.dingtalk.com/download/report.xlsx?'
        )
        for secret in (
            'token-plain-001',
            'signature-plain-001',
            'download-plain-001',
            signed_url,
        ):
            assert secret not in flattened
    finally:
        db.close()


def test_raw_metadata_is_bounded_and_marks_truncation_for_oversized_payload(monkeypatch) -> None:
    _allow_group(monkeypatch)
    oversized_text = '原始元数据' * 300
    nested = {'leaf': '最深层文本'}
    for level in range(gateway.RAW_METADATA_MAX_DEPTH + 3):
        nested = {f'level_{level}': nested}
    db = _db_session()
    try:
        result = gateway.ingest_dingtalk_stream_event(
            db,
            _text_payload(
                messageId='msg-raw-cap-001',
                msgtype='unknown_event',
                text=None,
                rawBlob=oversized_text,
                rawItems=[{'idx': index, 'note': oversized_text} for index in range(gateway.RAW_METADATA_MAX_ITEMS + 5)],
                msgParam=json.dumps(
                    {
                        'content': oversized_text,
                        'deep': nested,
                    },
                    ensure_ascii=False,
                ),
            ),
        )

        evidence = db.query(MultimodalEvidence).one()
        raw_metadata = evidence.payload['raw_metadata']
        assert result['accepted'] is True
        assert evidence.payload['trace_id'] == 'msg-raw-cap-001'
        assert evidence.payload['messageType'] == 'unknown_event'
        assert evidence.payload['group_id'] == 'group-001'
        assert evidence.payload['senderStaffId'] == 'staff-001'
        assert evidence.payload['eventTime'] == '2026-06-28T08:30:00+08:00'
        assert len(raw_metadata['rawBlob']) <= gateway.RAW_METADATA_MAX_STRING_LENGTH + len(
            gateway.RAW_METADATA_TRUNCATION_MARKER
        )
        assert raw_metadata['rawBlob'].endswith(gateway.RAW_METADATA_TRUNCATION_MARKER)
        assert raw_metadata['msgParam']['content'].endswith(gateway.RAW_METADATA_TRUNCATION_MARKER)
        assert len(raw_metadata['rawItems']) == gateway.RAW_METADATA_MAX_ITEMS + 1
        assert raw_metadata['rawItems'][-1] == gateway.RAW_METADATA_TRUNCATION_MARKER
        assert gateway.RAW_METADATA_TRUNCATION_MARKER in str(raw_metadata['msgParam']['deep'])
    finally:
        db.close()


def test_business_date_falls_back_to_business_time_helper(monkeypatch) -> None:
    _allow_group(monkeypatch)
    monkeypatch.setattr(
        gateway,
        'resolve_dingtalk_energy_business_date',
        lambda payload, *, file_name=None: date(2026, 7, 6),
    )
    db = _db_session()
    try:
        payload = _text_payload(messageId='msg-no-date')
        del payload['data']['businessDate']
        gateway.ingest_dingtalk_stream_event(db, payload)

        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['business_date'] == '2026-07-06'
    finally:
        db.close()


def test_excel_file_can_be_passed_to_existing_energy_ingest(monkeypatch) -> None:
    _allow_group(monkeypatch)
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = '日报'
    worksheet.append(['日期', '用电'])
    worksheet.append(['2026-07-07', 8440])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    content = buffer.getvalue()
    fake_dingtalk = FakeDingTalkService(
        result=dingtalk_service.DingTalkDownloadedFile(
            download_url_host='files.dingtalk.com',
            content=content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            size=len(content),
        )
    )
    calls = []

    def fake_energy_ingest(db, *, payload, evidence, trace_id):
        calls.append((payload, evidence.id, trace_id))
        assert payload['fileContentBase64']
        return {'status': 'promoted'}

    monkeypatch.setattr(gateway, 'ingest_dingtalk_energy_file', fake_energy_ingest)
    db = _db_session()
    try:
        payload = _file_payload(
            content={'fileName': '2026-07-07电耗.xlsx', 'downloadCode': 'download-code-001', 'fileId': 'file-001'}
        )
        result = gateway.ingest_dingtalk_stream_event(db, payload, dingtalk_service=fake_dingtalk)

        assert result['file_text'] is True
        assert result['energy_ingest'] == {'status': 'promoted'}
        assert len(calls) == 1
        assert calls[0][2] == 'file-msg-001'
    finally:
        db.close()
