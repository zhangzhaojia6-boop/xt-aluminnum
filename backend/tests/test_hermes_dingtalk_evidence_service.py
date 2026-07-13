from __future__ import annotations

from datetime import date, datetime
from typing import cast

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import MultimodalEvidence
from app.services import hermes_dingtalk_evidence_service as evidence_service
from app.services.hermes_dingtalk_evidence_service import query_dingtalk_evidence


def _db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[cast(Table, MultimodalEvidence.__table__)],
    )
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _add_evidence(
    db: Session,
    *,
    recognized_text: str | None,
    confirmation_status: str,
    payload: dict,
    evidence_type: str = "text",
    created_at: datetime | None = None,
    file_uri: str | None = None,
) -> MultimodalEvidence:
    row = MultimodalEvidence(
        evidence_type=evidence_type,
        recognized_text=recognized_text,
        confirmation_status=confirmation_status,
        payload=payload,
        created_at=created_at or datetime(2026, 6, 19, 9, 0),
        file_uri=file_uri,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_query_normalizes_message_file_attachment_and_recognized_text() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="会被 message_text 覆盖",
            confirmation_status="machine_only",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-message",
                "group_id": "cid-message",
                "dingtalk_sender_id": "user-message",
                "message_text": "产量 60 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="会被 file_text 覆盖",
            confirmation_status="specialist_sampled",
            evidence_type="attachment",
            file_uri="dingtalk://media/file-1",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-file",
                "conversationId": "cid-file",
                "dingtalk_sender_id": "user-file",
                "file_text": "日报总产量 62 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="附件文字 63 吨",
            confirmation_status="confirmed",
            evidence_type="attachment",
            file_uri="dingtalk://media/file-2",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-attachment",
                "group_id": "cid-attachment",
                "dingtalk_sender_id": "user-attachment",
                "attachment_text": "附件文字 63 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="只剩 recognized_text 也要能看见",
            confirmation_status="machine_only",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-recognized",
                "group_id": "cid-recognized",
                "dingtalk_sender_id": "user-recognized",
                "parse_status": "text_captured",
            },
        )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
        )

        assert [item.content_kind for item in items] == [
            "message_text",
            "file_text",
            "attachment_text",
            "recognized_text",
        ]
        assert [item.text for item in items] == [
            "产量 60 吨",
            "日报总产量 62 吨",
            "附件文字 63 吨",
            "只剩 recognized_text 也要能看见",
        ]
        assert items[0].group_id == "cid-message"
        assert items[1].conversation_id == "cid-file"
        assert items[2].sender_id == "user-attachment"
    finally:
        db.close()


@pytest.mark.parametrize(
    "date_key",
    ["business_date", "businessDate", "report_date", "reportDate", "target_date", "targetDate", "date"],
)
def test_query_supports_all_explicit_dingtalk_date_keys(date_key: str) -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="总产量 61 吨",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                date_key: "2026-06-19",
                "trace_id": f"trace-{date_key}",
                "message_text": "总产量 61 吨",
                "parse_status": "text_captured",
            },
        )

        item = query_dingtalk_evidence(db, business_date=date(2026, 6, 19))[0]

        assert item.business_date == date(2026, 6, 19)
        assert item.adoptable_as_fact is True
    finally:
        db.close()


def test_query_newest_first_keeps_latest_rows_under_limit() -> None:
    db = _db_session()
    try:
        for index in range(7):
            _add_evidence(
                db,
                recognized_text=f"第 {index} 条",
                confirmation_status="machine_only",
                payload={
                    "source": "dingtalk",
                    "business_date": "2026-06-19",
                    "trace_id": f"trace-{index}",
                    "message_text": f"第 {index} 条",
                    "parse_status": "text_captured",
                },
            )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            newest_first=True,
            limit=5,
        )

        assert [item.trace_id for item in items] == [
            "trace-6",
            "trace-5",
            "trace-4",
            "trace-3",
            "trace-2",
        ]
    finally:
        db.close()


def test_query_limit_does_not_let_newer_out_of_day_noise_hide_exact_target_date() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="目标日报 61 吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 19, 8, 0),
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-target",
                "message_text": "目标日报 61 吨",
                "parse_status": "text_captured",
            },
        )
        for index in range(2):
            _add_evidence(
                db,
                recognized_text="其他业务日消息",
                confirmation_status="machine_only",
                created_at=datetime(2026, 6, 20, 9, index),
                payload={
                    "source": "dingtalk",
                    "trace_id": f"trace-noise-{index}",
                    "event_time": f"2026-06-20T09:0{index}:00+08:00",
                    "message_text": "其他业务日消息",
                    "parse_status": "text_captured",
                },
            )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            newest_first=True,
            limit=2,
        )

        assert [item.trace_id for item in items] == ["trace-target"]
    finally:
        db.close()


def test_per_source_key_limit_keeps_latest_text_and_file_evidence() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="文件日报",
            confirmation_status="machine_only",
            evidence_type="attachment",
            file_uri="dingtalk://media/file-quota",
            created_at=datetime(2026, 6, 19, 8, 0),
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-file-quota",
                "file_text": "文件日报",
                "parse_status": "text_captured",
            },
        )
        for index in range(20):
            _add_evidence(
                db,
                recognized_text=f"群消息 {index}",
                confirmation_status="machine_only",
                created_at=datetime(2026, 6, 19, 9, index),
                payload={
                    "source": "dingtalk",
                    "business_date": "2026-06-19",
                    "trace_id": f"trace-text-quota-{index}",
                    "message_text": f"群消息 {index}",
                    "parse_status": "text_captured",
                },
            )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            newest_first=True,
            per_source_key_limit=1,
        )

        assert [item.source_key for item in items] == [
            "dingtalk_group_content",
            "dingtalk_group_file",
        ]
        assert items[0].trace_id == "trace-text-quota-19"
        assert items[1].trace_id == "trace-file-quota"
    finally:
        db.close()


def test_include_outside_context_keeps_target_fact_before_newer_diagnostics() -> None:
    db = _db_session()
    try:
        for trace_id, fact_date, created_at in (
            ("trace-target", "2026-06-19", datetime(2026, 6, 19, 8, 0)),
            ("trace-outside-1", "2026-06-20", datetime(2026, 6, 20, 9, 0)),
            ("trace-outside-2", "2026-06-21", datetime(2026, 6, 21, 9, 0)),
        ):
            _add_evidence(
                db,
                recognized_text=trace_id,
                confirmation_status="confirmed",
                created_at=created_at,
                payload={
                    "source": "dingtalk",
                    "business_date": fact_date,
                    "trace_id": trace_id,
                    "message_text": trace_id,
                    "parse_status": "text_captured",
                },
            )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            include_outside_business_context=True,
            newest_first=True,
            limit=2,
        )

        assert [item.trace_id for item in items] == ["trace-target", "trace-outside-2"]
        oldest_first = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            include_outside_business_context=True,
            newest_first=False,
            limit=2,
        )
        assert [item.trace_id for item in oldest_first] == ["trace-target", "trace-outside-1"]
    finally:
        db.close()


@pytest.mark.parametrize(
    "body_text",
    ["2026-06-19 总产量 61 吨", "2026年6月19日总产量 61 吨"],
)
def test_body_date_candidate_is_prioritized_inside_scan_cap(monkeypatch, body_text: str) -> None:
    db = _db_session()
    monkeypatch.setattr(evidence_service, "MAX_QUERY_LIMIT", 3)
    try:
        _add_evidence(
            db,
            recognized_text=body_text,
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 18, 8, 0),
            payload={
                "source": "dingtalk",
                "trace_id": "trace-body-date-target",
                "message_text": body_text,
                "parse_status": "text_captured",
            },
        )
        for index in range(3):
            _add_evidence(
                db,
                recognized_text="外日噪声",
                confirmation_status="machine_only",
                created_at=datetime(2026, 6, 20, 9, index),
                payload={
                    "source": "dingtalk",
                    "trace_id": f"trace-scan-noise-{index}",
                    "event_time": f"2026-06-20T09:0{index}:00+08:00",
                    "message_text": "外日噪声",
                    "parse_status": "text_captured",
                },
            )

        items = query_dingtalk_evidence(db, business_date=date(2026, 6, 19), limit=1)

        assert [item.trace_id for item in items] == ["trace-body-date-target"]
    finally:
        db.close()


def test_content_channel_filter_applies_before_per_source_quota() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="群内目标消息",
            confirmation_status="machine_only",
            created_at=datetime(2026, 6, 19, 8, 0),
            payload={
                "source": "dingtalk",
                "channel": "dingtalk_group",
                "business_date": "2026-06-19",
                "trace_id": "trace-group-target",
                "message_text": "群内目标消息",
                "parse_status": "text_captured",
            },
        )
        for index in range(5):
            _add_evidence(
                db,
                recognized_text="单聊消息",
                confirmation_status="machine_only",
                created_at=datetime(2026, 6, 19, 9, index),
                payload={
                    "source": "dingtalk",
                    "channel": "dingtalk_private",
                    "business_date": "2026-06-19",
                    "trace_id": f"trace-private-{index}",
                    "message_text": "单聊消息",
                    "parse_status": "text_captured",
                },
            )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            newest_first=True,
            limit=5,
            per_source_key_limit=5,
            content_channels=("dingtalk_group",),
        )

        assert [item.trace_id for item in items] == ["trace-group-target"]
    finally:
        db.close()


def test_total_limit_still_applies_with_per_source_quota() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="文本",
            confirmation_status="machine_only",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-limit-text",
                "message_text": "文本",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="文件",
            confirmation_status="machine_only",
            evidence_type="attachment",
            file_uri="dingtalk://media/limit-file",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-limit-file",
                "file_text": "文件",
                "parse_status": "text_captured",
            },
        )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            newest_first=True,
            limit=1,
            per_source_key_limit=1,
        )

        assert len(items) == 1
    finally:
        db.close()


def test_machine_only_is_visible_to_hermes_but_not_adoptable() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="产量大概六十吨",
            confirmation_status="machine_only",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-machine-only",
                "message_text": "产量大概六十吨",
                "parse_status": "text_captured",
            },
        )

        item = query_dingtalk_evidence(db, business_date=date(2026, 6, 19))[0]

        assert item.visible_to_hermes is True
        assert item.adoptable_as_fact is False
    finally:
        db.close()


def test_missing_parse_status_stays_visible_but_is_not_adoptable() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="产量 60 吨",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-missing-parse-status",
                "message_text": "产量 60 吨",
            },
        )

        item = query_dingtalk_evidence(db, business_date=date(2026, 6, 19))[0]

        assert item.visible_to_hermes is True
        assert item.parse_status == "unknown"
        assert item.adoptable_as_fact is False
    finally:
        db.close()


def test_specialist_sampled_and_confirmed_are_adoptable_only_when_date_and_trace_match() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="总产量 61 吨",
            confirmation_status="specialist_sampled",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-specialist",
                "message_text": "总产量 61 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="总产量 62 吨",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-confirmed",
                "message_text": "总产量 62 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="总产量 63 吨",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-18",
                "trace_id": "trace-date-mismatch",
                "message_text": "总产量 63 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text="总产量 64 吨",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "id": "event-id-is-not-a-trace",
                "message_text": "总产量 64 吨",
                "parse_status": "text_captured",
            },
        )
        _add_evidence(
            db,
            recognized_text=None,
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-no-text",
                "message_text": "",
                "parse_status": "text_unavailable",
            },
        )

        items = query_dingtalk_evidence(
            db,
            business_date=date(2026, 6, 19),
            include_outside_business_context=True,
        )
        adoptable_by_trace = {item.trace_id: item.adoptable_as_fact for item in items}

        assert adoptable_by_trace["trace-specialist"] is True
        assert adoptable_by_trace["trace-confirmed"] is True
        assert adoptable_by_trace["trace-date-mismatch"] is False
        assert adoptable_by_trace.get("") is False
        assert adoptable_by_trace["trace-no-text"] is False
        no_text = next(item for item in items if item.trace_id == "trace-no-text")
        assert no_text.visible_to_hermes is True
    finally:
        db.close()


def test_query_excludes_unrelated_historical_evidence() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="旧日报产量 40 吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 10, 9, 0),
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-10",
                "trace_id": "trace-old",
                "message_text": "旧日报产量 40 吨",
                "parse_status": "text_captured",
            },
        )

        assert query_dingtalk_evidence(db, business_date=date(2026, 6, 19)) == []
    finally:
        db.close()


def test_query_does_not_misclassify_generic_traced_evidence_as_dingtalk() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="其他系统确认产量 66 吨",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-06-19",
                "trace_id": "trace-other-system",
                "group_id": "other-chat-group",
                "message_text": "其他系统确认产量 66 吨",
                "fact_updates": {"total_output_daily": {"value": 66}},
                "parse_status": "text_captured",
            },
        )

        assert query_dingtalk_evidence(db, business_date=date(2026, 6, 19)) == []
    finally:
        db.close()


@pytest.mark.parametrize("workshop_name", ["铸二", "铸三车间", "热轧"])
def test_special_workshop_today_uses_1000_business_boundary(workshop_name: str) -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="今日总产量 61 吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 3, 9, 0),
            payload={
                "source": "dingtalk",
                "workshop_name": workshop_name,
                "trace_id": f"trace-{workshop_name}",
                "message_text": "今日总产量 61 吨",
                "parse_status": "text_captured",
            },
        )

        previous_day = query_dingtalk_evidence(db, business_date=date(2026, 6, 2))
        current_day = query_dingtalk_evidence(db, business_date=date(2026, 6, 3))

        assert len(previous_day) == 1
        assert previous_day[0].business_date == date(2026, 6, 2)
        assert previous_day[0].adoptable_as_fact is True
        assert current_day == []
    finally:
        db.close()


def test_today_without_workshop_does_not_infer_adoptable_business_date() -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="今日总产量 61 吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 3, 9, 0),
            payload={
                "source": "dingtalk",
                "trace_id": "trace-unknown-workshop",
                "message_text": "今日总产量 61 吨",
                "parse_status": "text_captured",
            },
        )

        item = query_dingtalk_evidence(db, business_date=date(2026, 6, 3))[0]

        assert item.business_date is None
        assert item.visible_to_hermes is True
        assert item.adoptable_as_fact is False
    finally:
        db.close()


@pytest.mark.parametrize("workshop_name", ["UNKNOWN_WORKSHOP", "铸二错字", "ZR2"])
def test_today_with_unknown_workshop_does_not_infer_adoptable_business_date(workshop_name: str) -> None:
    db = _db_session()
    try:
        _add_evidence(
            db,
            recognized_text="今日总产量 61 吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 3, 8, 0),
            payload={
                "source": "dingtalk",
                "workshop_name": workshop_name,
                "trace_id": f"trace-{workshop_name}",
                "message_text": "今日总产量 61 吨",
                "parse_status": "text_captured",
            },
        )

        item = query_dingtalk_evidence(db, business_date=date(2026, 6, 3))[0]

        assert item.workshop_name is None
        assert item.business_date is None
        assert item.visible_to_hermes is True
        assert item.adoptable_as_fact is False
    finally:
        db.close()
