from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentEvent, MultimodalEvidence
from app.services import agent_multimodal_evidence_service as evidence_service


class _TrackingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False
        self.committed = False
        self.refreshed: list[object] = []

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        self.refreshed.append(item)


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _event(db) -> AgentEvent:
    event = AgentEvent(
        event_type='machine_photo_received',
        severity='info',
        status='pending',
        scope_type='workshop',
        workshop_id=2,
        source_type='dingtalk_multimodal',
        source_ref='trace-evidence-001',
        business_date=date(2026, 6, 13),
        payload={'trace_id': 'trace-evidence-001'},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_record_image_evidence_is_machine_only_and_traceable() -> None:
    db = _db_session()
    try:
        event = _event(db)

        evidence = evidence_service.record_evidence(
            db,
            evidence_type='image',
            file_uri='dingtalk://media/image-001',
            event_id=event.id,
            recognized_text='随行卡 26A04967，下机重量 6350kg',
            source_user_id=7,
            source_channel_id=3,
            payload={'media_id': 'image-001', 'source': 'dingtalk'},
        )

        assert evidence.id is not None
        assert evidence.event_id == event.id
        assert evidence.evidence_type == 'image'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.recognized_text == '随行卡 26A04967，下机重量 6350kg'
        assert evidence.payload['metric_write_allowed'] is False
        assert evidence.payload['source'] == 'dingtalk'
    finally:
        db.close()


def test_record_voice_evidence_accepts_transcript_without_metric_write() -> None:
    db = _db_session()
    try:
        event = _event(db)

        evidence = evidence_service.record_evidence(
            db,
            evidence_type='voice',
            file_uri='dingtalk://media/voice-001',
            event_id=event.id,
            recognized_text='热轧停机四十五分钟，等待维修确认',
            payload={'duration_seconds': 18},
        )

        assert evidence.evidence_type == 'voice'
        assert evidence.confirmation_status == 'machine_only'
        assert evidence.payload['metric_write_allowed'] is False
        assert evidence.payload['duration_seconds'] == 18
    finally:
        db.close()


def test_record_evidence_rejects_unknown_type() -> None:
    db = _db_session()
    try:
        with pytest.raises(evidence_service.MultimodalEvidenceError, match='unsupported_evidence_type'):
            evidence_service.record_evidence(
                db,
                evidence_type='spreadsheet',
                file_uri='dingtalk://media/xls-001',
            )
    finally:
        db.close()


def test_record_evidence_commit_false_flushes_without_commit_or_refresh() -> None:
    db = _TrackingSession()

    evidence = evidence_service.record_evidence(
        db,
        evidence_type='text',
        file_uri=None,
        recognized_text='日报产量 32 吨',
        payload={'source': 'dingtalk'},
        commit=False,
    )

    assert db.added == [evidence]
    assert db.flushed is True
    assert db.committed is False
    assert db.refreshed == []
    assert evidence.payload['metric_write_allowed'] is False


def test_record_evidence_default_still_commits_and_refreshes() -> None:
    db = _TrackingSession()

    evidence = evidence_service.record_evidence(
        db,
        evidence_type='text',
        file_uri=None,
        recognized_text='日报产量 32 吨',
    )

    assert db.added == [evidence]
    assert db.committed is True
    assert db.refreshed == [evidence]
    assert db.flushed is False


def test_confirm_evidence_changes_status_but_still_does_not_write_metrics() -> None:
    db = _db_session()
    try:
        evidence = evidence_service.record_evidence(
            db,
            evidence_type='attachment',
            file_uri='dingtalk://media/file-001',
            recognized_text='交接班附件',
            payload={'file_name': '交接班.txt'},
        )

        confirmed = evidence_service.mark_human_confirmed(
            db,
            evidence.id,
            confirmer_user_id=9,
            result_payload={'确认结果': '附件可作为异常备案'},
        )

        assert confirmed.confirmation_status == 'human_confirmed'
        assert confirmed.payload['metric_write_allowed'] is False
        assert confirmed.payload['confirmed_by_user_id'] == 9
        assert confirmed.payload['confirm_result']['确认结果'] == '附件可作为异常备案'
    finally:
        db.close()


def test_list_event_evidence_returns_only_that_event() -> None:
    db = _db_session()
    try:
        first_event = _event(db)
        second_event = _event(db)
        first = evidence_service.record_evidence(
            db,
            evidence_type='image',
            file_uri='dingtalk://media/image-001',
            event_id=first_event.id,
        )
        evidence_service.record_evidence(
            db,
            evidence_type='image',
            file_uri='dingtalk://media/image-002',
            event_id=second_event.id,
        )

        rows = evidence_service.list_event_evidence(db, event_id=first_event.id)

        assert [row.id for row in rows] == [first.id]
        assert db.query(MultimodalEvidence).count() == 2
    finally:
        db.close()


def test_record_dingtalk_media_message_maps_image_payload_to_evidence() -> None:
    db = _db_session()
    try:
        event = _event(db)

        evidence = evidence_service.record_dingtalk_media_message(
            db,
            {
                'msgtype': 'image',
                'mediaId': 'media-image-001',
                'senderStaffId': 'dt-user-001',
                'conversationId': 'cid-test',
                'msgId': 'msg-image-001',
            },
            event_id=event.id,
            recognized_text='随行卡 26A04967',
        )

        assert evidence.evidence_type == 'image'
        assert evidence.file_uri == 'dingtalk://media/media-image-001'
        assert evidence.event_id == event.id
        assert evidence.payload['dingtalk_sender_id'] == 'dt-user-001'
        assert evidence.payload['dingtalk_conversation_id'] == 'cid-test'
        assert evidence.payload['metric_write_allowed'] is False
    finally:
        db.close()


def test_record_dingtalk_media_message_rejects_unhandled_message_type() -> None:
    db = _db_session()
    try:
        with pytest.raises(evidence_service.MultimodalEvidenceError, match='unsupported_dingtalk_message_type'):
            evidence_service.record_dingtalk_media_message(
                db,
                {
                    'msgtype': 'video',
                    'mediaId': 'media-video-001',
                },
            )
    finally:
        db.close()
