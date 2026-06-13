from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentEvent, AgentOperationApproval
from app.models.reports import DailyReport
from app.models.system import User
from app.services import agent_communication_service as communication_service
from app.services import agent_designated_operation_service as designated_service


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _management_channel(db) -> None:
    communication_service.register_channel(
        db,
        channel_type='dingtalk_group',
        channel_key='management-chat',
        name='管理总控群',
        target_type='management',
        target_key='management',
    )


def _user(db, user_id: int = 7) -> User:
    user = User(
        id=user_id,
        username=f'user-{user_id}',
        password_hash='test',
        name=f'指定人员{user_id}',
        role='admin',
        dingtalk_user_id=f'dd-{user_id}',
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _daily_report(db, *, body: str = '今日日报正文') -> DailyReport:
    report = DailyReport(
        report_date=date(2026, 6, 13),
        report_type='factory_daily',
        report_data={'source': 'unit_test'},
        final_text_summary=body,
        quality_gate_status='passed',
        delivery_ready=True,
        status='ready',
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def test_supplement_preview_requires_designated_user_and_valid_payload() -> None:
    db = _db_session()
    try:
        _management_channel(db)

        with pytest.raises(designated_service.AgentDesignatedOperationError, match='requester_not_allowed'):
            designated_service.request_supplement_production_preview(
                db,
                requester_user_id=99,
                channel_key='management-chat',
                allowed_user_ids={7},
                payload={
                    'business_date': '2026-06-13',
                    'workshop_name': '热轧',
                    'tons': 12.5,
                    'reason': '坯料卷补录',
                },
            )

        with pytest.raises(designated_service.AgentDesignatedOperationError, match='tons_required'):
            designated_service.request_supplement_production_preview(
                db,
                requester_user_id=7,
                channel_key='management-chat',
                allowed_user_ids={7},
                payload={
                    'business_date': '2026-06-13',
                    'workshop_name': '热轧',
                    'reason': '坯料卷补录',
                },
            )

        assert db.query(AgentOperationApproval).count() == 0
    finally:
        db.close()


def test_supplement_preview_and_execution_create_auditable_event_not_mes_write() -> None:
    db = _db_session()
    try:
        _management_channel(db)
        _user(db, 7)

        approval = designated_service.request_supplement_production_preview(
            db,
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            payload={
                'business_date': '2026-06-13',
                'workshop_name': '热轧',
                'tons': 12.5,
                'reason': '坯料卷补录',
            },
            trace_id='trace-stage7-supplement',
        )

        preview = approval.preview_payload
        assert approval.status == 'pending_confirmation'
        assert preview['metric_write_allowed'] is False
        assert preview['report_publish_allowed'] is False
        assert preview['payload']['write_target'] == 'agent_events.production_supplement_requested'
        assert preview['payload']['changes_core_production_tables'] is False

        designated_service.confirm_designated_operation(
            db,
            approval.id,
            approver_user_id=7,
            allowed_user_ids={7},
            confirmation_text='确认进入人工纠偏队列',
        )
        executed = designated_service.execute_designated_operation(
            db,
            approval.id,
            executor_user_id=7,
            allowed_user_ids={7},
            dry_run=False,
        )

        event = db.query(AgentEvent).one()
        assert event.event_type == 'production_supplement_requested'
        assert event.status == 'pending_manual_apply'
        assert event.business_date == date(2026, 6, 13)
        assert event.payload['tons'] == 12.5
        assert event.payload['source_approval_id'] == approval.id
        assert event.payload['changes_mes_original_data'] is False
        assert executed.status == 'executed'
        assert executed.result_payload['executor_result']['write_target'] == 'agent_events'
    finally:
        db.close()


def test_publish_preview_requires_report_body_and_keeps_text_hash() -> None:
    db = _db_session()
    try:
        _management_channel(db)
        report = _daily_report(db, body='6月13日鑫泰铝业数据中枢日报')

        approval = designated_service.request_publish_daily_report_preview(
            db,
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            report_id=report.id,
            recipient_user_ids=[7],
            trace_id='trace-stage7-publish',
        )

        payload = approval.preview_payload['payload']
        assert approval.status == 'pending_confirmation'
        assert approval.preview_payload['report_publish_allowed'] is False
        assert payload['report_id'] == report.id
        assert payload['report_date'] == '2026-06-13'
        assert payload['preview_text'] == '6月13日鑫泰铝业数据中枢日报'
        assert len(payload['final_text_sha256']) == 64
        assert payload['report_publish_allowed_after_confirmation'] is True
    finally:
        db.close()


def test_publish_execution_rejects_changed_report_after_preview() -> None:
    db = _db_session()
    try:
        _management_channel(db)
        _user(db, 7)
        report = _daily_report(db, body='预览时的日报正文')
        approval = designated_service.request_publish_daily_report_preview(
            db,
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            report_id=report.id,
        )
        designated_service.confirm_designated_operation(db, approval.id, approver_user_id=7, allowed_user_ids={7})

        report.final_text_summary = '确认后被修改的日报正文'
        db.commit()

        with pytest.raises(designated_service.AgentDesignatedOperationError, match='report_preview_changed'):
            designated_service.execute_designated_operation(
                db,
                approval.id,
                executor_user_id=7,
                allowed_user_ids={7},
                dry_run=False,
                daily_report_publisher=lambda **_kwargs: {'sent_count': 1},
            )
    finally:
        db.close()


def test_publish_execution_calls_existing_publisher_after_confirmation() -> None:
    db = _db_session()
    calls: list[dict] = []
    try:
        _management_channel(db)
        operator = _user(db, 7)
        report = _daily_report(db, body='最终确认后的日报正文')
        approval = designated_service.request_publish_daily_report_preview(
            db,
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            report_id=report.id,
            recipient_user_ids=[7],
        )
        designated_service.confirm_designated_operation(db, approval.id, approver_user_id=7, allowed_user_ids={7})

        def fake_publisher(**kwargs):
            calls.append(kwargs)
            return {'sent_count': 1, 'failed': [], 'recipients': 1}

        executed = designated_service.execute_designated_operation(
            db,
            approval.id,
            executor_user_id=7,
            allowed_user_ids={7},
            dry_run=False,
            daily_report_publisher=fake_publisher,
        )

        assert calls == [
            {
                'db': db,
                'report_id': report.id,
                'operator': operator,
                'recipient_user_ids': [7],
            }
        ]
        assert executed.status == 'executed'
        assert executed.result_payload['executor_result']['sent_count'] == 1
        assert executed.result_payload['actual_write'] is True
    finally:
        db.close()
