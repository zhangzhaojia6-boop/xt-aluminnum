from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import unicodedata

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import ChatInboxMessage, DingTalkInboundReceipt, MultimodalEvidence
from app.models.base import Base
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_dingtalk_stream_evidence_gate.py'
TABLES = [
    ChatInboxMessage.__table__,
    DingTalkInboundReceipt.__table__,
    MultimodalEvidence.__table__,
]


def _load_script_module():
    spec = spec_from_file_location('check_dingtalk_stream_evidence_gate', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _session() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _normalized_sha256(value: str) -> str:
    normalized = ' '.join(unicodedata.normalize('NFKC', value).strip().split())
    return _sha256(normalized)


def _seed_valid_acceptance(db: Session, *, marker: str) -> tuple[list[dict], str, str, list[str]]:
    ledger: list[dict] = []
    traces: list[str] = []
    text_values = [
        f'{marker}  Ａ班   产量 32 吨',
        f'{marker}\t私聊复核\n入库 31 吨',
        *[f'{marker} 文本验收 {index}' for index in range(3, 11)],
    ]
    file_names = [
        f'{marker}-现场图.png',
        f'{marker}-能耗.xlsx',
        f'{marker}-日报.pdf',
        f'{marker}-说明.txt',
        f'{marker}-明细.csv',
    ]

    for index in range(15):
        trace_id = f'trace-acceptance-{index:02d}'
        traces.append(trace_id)
        is_file = index >= 10
        is_private = index in {1, 10}
        channel = 'dingtalk_private' if is_private else 'dingtalk_group'
        group_id = None if is_private else 'conversation-acceptance-group'
        inbox_text = file_names[index - 10] if is_file else text_values[index]
        db.add(
            DingTalkInboundReceipt(
                dedupe_key=_sha256(f'receipt:{trace_id}'),
                channel=channel,
                group_id=group_id,
                trace_id=trace_id,
                status='completed_evidence',
            )
        )
        db.add(
            ChatInboxMessage(
                channel=channel,
                group_id=group_id,
                sender_external_id=f'sender-{index:02d}',
                text=inbox_text,
                trace_id=trace_id,
                inbound_dedupe_key=_sha256(f'inbox:{trace_id}'),
                source_payload={'source_transport': 'dingtalk_stream'},
            )
        )

        if is_file:
            file_index = index - 10
            parse_status = 'text_unavailable' if file_index == 0 else 'text_captured'
            recognized_text = None if parse_status != 'text_captured' else f'{marker} 文件正文 {file_index}'
            evidence_payload = {
                'source': 'dingtalk',
                'source_transport': 'dingtalk_stream',
                'trace_id': trace_id,
                'channel': channel,
                'group_id': group_id,
                'conversation_id': 'private-file-conversation' if is_private else None,
                'file_name': file_names[file_index],
                'file_hash': _sha256(f'file:{trace_id}'),
                'parse_status': parse_status,
                'business_date': '2026-07-15',
                'business_date_status': 'filename_explicit',
                'dingtalk_sender_id': f'sender-{index:02d}',
                'dingtalk_message_time': '2026-07-16T08:30:00+08:00',
            }
            if recognized_text:
                evidence_payload['file_text'] = recognized_text
            evidence = MultimodalEvidence(
                evidence_type='attachment',
                recognized_text=recognized_text,
                payload=evidence_payload,
            )
            message_type = 'file'
        else:
            evidence = MultimodalEvidence(
                evidence_type='text',
                recognized_text=text_values[index],
                payload={
                    'source': 'dingtalk',
                    'source_transport': 'dingtalk_stream',
                    'trace_id': trace_id,
                    'channel': channel,
                    'group_id': group_id,
                    'message_text': text_values[index],
                    'parse_status': 'text_captured',
                    'business_date': '2026-07-15',
                    'business_date_status': 'payload_explicit',
                    'dingtalk_sender_id': f'sender-{index:02d}',
                    'dingtalk_message_time': '2026-07-16T08:30:00+08:00',
                },
            )
            message_type = 'text'
        db.add(evidence)
        ledger.append(
            {
                'trace_hash': _sha256(trace_id),
                'message_type': 'picture' if index == 10 else message_type,
                'channel_type': 'private' if is_private else 'group',
                'callback_receive_time': '2026-07-16T08:30:01+08:00',
                'source': 'stream_callback',
            }
        )

    db.commit()
    return ledger, _normalized_sha256(text_values[0]), _normalized_sha256(text_values[1]), traces


def _inspect(module, db: Session, *, marker: str, ledger: list[dict], u1: str, u2: str):
    return module.inspect_dingtalk_stream_evidence_gate(
        db,
        marker=marker,
        min_text=10,
        min_files=5,
        since=datetime(2026, 7, 1, tzinfo=timezone.utc),
        hermes_ledger=ledger,
        expected_u1_sha256=u1,
        expected_u2_sha256=u2,
    )


def test_gate_passes_only_complete_real_stream_evidence() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-RAW-MARKER'
    db = _session()
    try:
        ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
        counts_before = (
            db.query(DingTalkInboundReceipt).count(),
            db.query(ChatInboxMessage).count(),
            db.query(MultimodalEvidence).count(),
        )

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)
        repeated = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)

        assert payload['status'] == 'PASS'
        assert repeated == payload
        assert counts_before == (
            db.query(DingTalkInboundReceipt).count(),
            db.query(ChatInboxMessage).count(),
            db.query(MultimodalEvidence).count(),
        )
        assert payload['blockers'] == []
        assert set(payload) == {'status', 'blockers', 'marker_sha256', 'trace_hashes', 'counts'}
        assert payload['counts']['text_count'] == 10
        assert payload['counts']['file_count'] == 5
        assert payload['counts']['image_file_count'] == 1
        assert payload['counts']['xlsx_file_count'] == 1
        assert payload['counts']['pdf_file_count'] == 1
        assert payload['counts']['text_captured_file_count'] == 4
        assert payload['counts']['group_trace_count'] == 13
        assert payload['counts']['private_trace_count'] == 2
    finally:
        db.close()


def test_gate_blocks_missing_callback_and_invented_file_text() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-BLOCK-MARKER'
    db = _session()
    try:
        ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
        ledger.pop()
        ledger[0]['message_text'] = 'raw text must never enter callback proof ledger'
        image = (
            db.query(MultimodalEvidence)
            .filter(MultimodalEvidence.evidence_type == 'attachment')
            .order_by(MultimodalEvidence.id.asc())
            .first()
        )
        assert image is not None
        image.recognized_text = 'invented attachment text'
        db.commit()

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)

        codes = {item['code'] for item in payload['blockers']}
        assert payload['status'] == 'BLOCKED'
        assert 'LEDGER_CALLBACK_MISSING' in codes
        assert 'LEDGER_ENTRY_SCHEMA_INVALID' in codes
        assert 'FILE_TEXT_INVENTED' in codes
    finally:
        db.close()


def test_gate_keeps_filename_marker_requirement_for_file_candidates() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-FILENAME-MARKER'
    db = _session()
    try:
        ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
        file_evidence = (
            db.query(MultimodalEvidence)
            .filter(MultimodalEvidence.evidence_type == 'attachment')
            .order_by(MultimodalEvidence.id.asc())
            .first()
        )
        assert file_evidence is not None
        file_evidence.payload = {
            **file_evidence.payload,
            'file_name': '现场图.png',
            'message_text': f'{marker} 文件候选消息',
        }
        db.commit()

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)

        assert 'FILE_MARKER_MISSING' in {item['code'] for item in payload['blockers']}
    finally:
        db.close()


def test_gate_blocks_incomplete_receipt_and_invalid_text_business_date_status() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-STATE-MARKER'
    db = _session()
    try:
        ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
        receipt = db.query(DingTalkInboundReceipt).order_by(DingTalkInboundReceipt.id.asc()).first()
        text_evidence = (
            db.query(MultimodalEvidence)
            .filter(MultimodalEvidence.evidence_type == 'text')
            .order_by(MultimodalEvidence.id.asc())
            .first()
        )
        assert receipt is not None and text_evidence is not None
        receipt.status = 'evidence_pending'
        text_evidence.payload = {**text_evidence.payload, 'business_date_status': 'model_guessed'}
        db.commit()

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)

        codes = {item['code'] for item in payload['blockers']}
        assert 'RECEIPT_STATUS_INCOMPLETE' in codes
        assert 'BUSINESS_DATE_STATUS_INVALID' in codes
    finally:
        db.close()


def test_gate_blocks_old_event_and_callback_replayed_after_since() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-REPLAY-MARKER'
    db = _session()
    try:
        ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
        evidence = db.query(MultimodalEvidence).order_by(MultimodalEvidence.id.asc()).first()
        assert evidence is not None
        evidence.payload = {
            **evidence.payload,
            'dingtalk_message_time': '2026-06-30T23:59:59+00:00',
        }
        ledger[0]['callback_receive_time'] = '2026-06-30T23:59:59+00:00'
        db.commit()

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)

        codes = {item['code'] for item in payload['blockers']}
        assert 'EVENT_TIME_BEFORE_SINCE' in codes
        assert 'CALLBACK_TIME_BEFORE_SINCE' in codes
    finally:
        db.close()


def test_gate_blocks_cross_table_rows_that_only_share_trace_id() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-CORRELATION-MARKER'
    db = _session()
    try:
        ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
        receipt = db.query(DingTalkInboundReceipt).order_by(DingTalkInboundReceipt.id.asc()).first()
        evidence = db.query(MultimodalEvidence).order_by(MultimodalEvidence.id.asc()).first()
        assert receipt is not None and evidence is not None
        receipt.channel = 'dingtalk_private'
        evidence.recognized_text = 'different text'
        evidence.payload = {
            **evidence.payload,
            'channel': 'dingtalk_private',
            'dingtalk_sender_id': 'different-sender',
            'message_text': 'different text',
        }
        db.commit()

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)

        codes = {item['code'] for item in payload['blockers']}
        assert 'TRACE_RECEIPT_SCOPE_MISMATCH' in codes
        assert 'TRACE_EVIDENCE_SCOPE_MISMATCH' in codes
        assert 'TRACE_SENDER_MISMATCH' in codes
        assert 'TRACE_TEXT_MISMATCH' in codes
    finally:
        db.close()


def test_gate_report_never_contains_raw_acceptance_data() -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-SECRET-MARKER'
    db = _session()
    try:
        ledger, u1, u2, traces = _seed_valid_acceptance(db, marker=marker)

        payload = _inspect(module, db, marker=marker, ledger=ledger, u1=u1, u2=u2)
        serialized = json.dumps(payload, ensure_ascii=False)

        assert payload['marker_sha256'] == _sha256(marker)
        assert marker not in serialized
        assert 'conversation-acceptance-group' not in serialized
        assert 'sender-00' not in serialized
        assert traces[0] not in serialized
        assert f'{marker}-能耗.xlsx' not in serialized
        assert len(payload['trace_hashes']) == 15
        assert 'D:\\输出skill' not in SCRIPT_PATH.read_text(encoding='utf-8')
    finally:
        db.close()


def test_gate_main_writes_sanitized_json_and_returns_nonzero_on_failure(tmp_path: Path, capsys) -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-CLI-MARKER'
    db = _session()
    ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
    engine = db.get_bind()
    db.close()
    ledger_path = tmp_path / 'ledger.json'
    ledger_path.write_text(json.dumps({'entries': ledger[:-1]}), encoding='utf-8')
    output_path = tmp_path / 'gate.json'
    SessionFactory = sessionmaker(bind=engine)

    exit_code = module.main(
        [
            '--marker',
            marker,
            '--since',
            '2026-07-01T00:00:00+00:00',
            '--hermes-ledger',
            str(ledger_path),
            '--expected-u1-sha256',
            u1,
            '--expected-u2-sha256',
            u2,
            '--output-json',
            str(output_path),
        ],
        session_factory=SessionFactory,
    )

    stdout = capsys.readouterr().out
    written = output_path.read_text(encoding='utf-8')
    assert exit_code == 2
    assert 'LEDGER_CALLBACK_MISSING' in stdout
    assert marker not in stdout
    assert marker not in written


def test_gate_main_resolves_default_session_factory_lazily(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    marker = 'XT-ACCEPT-CLI-DEFAULT-SESSION'
    db = _session()
    ledger, u1, u2, _ = _seed_valid_acceptance(db, marker=marker)
    engine = db.get_bind()
    db.close()
    ledger_path = tmp_path / 'ledger.json'
    ledger_path.write_text(json.dumps({'entries': ledger}), encoding='utf-8')
    output_path = tmp_path / 'gate.json'
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(module, 'get_sessionmaker', lambda: SessionFactory, raising=False)

    exit_code = module.main(
        [
            '--marker',
            marker,
            '--since',
            '2026-07-01T00:00:00+00:00',
            '--hermes-ledger',
            str(ledger_path),
            '--expected-u1-sha256',
            u1,
            '--expected-u2-sha256',
            u2,
            '--output-json',
            str(output_path),
        ],
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding='utf-8'))['status'] == 'PASS'
