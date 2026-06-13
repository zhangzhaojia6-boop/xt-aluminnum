from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentOperationApproval
from app.services import agent_communication_service as communication_service
from app.services import agent_operation_approval_service as approval_service


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


def test_request_operation_preview_rejects_unauthorized_user() -> None:
    db = _db_session()
    try:
        _management_channel(db)

        with pytest.raises(approval_service.AgentOperationApprovalError, match='requester_not_allowed'):
            approval_service.request_operation_preview(
                db,
                operation_type='supplement_production',
                requester_user_id=99,
                channel_key='management-chat',
                allowed_user_ids={7},
                preview_payload={'business_date': date(2026, 6, 13).isoformat(), 'tons': 12.5},
            )

        assert db.query(AgentOperationApproval).count() == 0
    finally:
        db.close()


def test_request_supplement_production_preview_records_gate_without_metric_write() -> None:
    db = _db_session()
    try:
        _management_channel(db)

        approval = approval_service.request_operation_preview(
            db,
            operation_type='supplement_production',
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            preview_payload={
                'business_date': '2026-06-13',
                'workshop_name': '热轧',
                'tons': 12.5,
                'reason': '坯料卷补录预览',
            },
            trace_id='trace-op-001',
        )

        assert approval.status == 'pending_confirmation'
        assert approval.operation_type == 'supplement_production'
        assert approval.requester_user_id == 7
        assert approval.trace_id == 'trace-op-001'
        assert approval.preview_payload['metric_write_allowed'] is False
        assert approval.preview_payload['report_publish_allowed'] is False
        assert approval.preview_payload['payload']['tons'] == 12.5
    finally:
        db.close()


def test_execute_rejects_unconfirmed_operation() -> None:
    db = _db_session()
    try:
        _management_channel(db)
        approval = approval_service.request_operation_preview(
            db,
            operation_type='publish_daily_report',
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            preview_payload={'business_date': '2026-06-13', 'report_id': 18},
        )

        with pytest.raises(approval_service.AgentOperationApprovalError, match='operation_not_confirmed'):
            approval_service.execute_confirmed_operation(db, approval.id)
    finally:
        db.close()


def test_confirm_operation_requires_allowed_approver_and_keeps_preview() -> None:
    db = _db_session()
    try:
        _management_channel(db)
        approval = approval_service.request_operation_preview(
            db,
            operation_type='publish_daily_report',
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            preview_payload={'business_date': '2026-06-13', 'report_id': 18},
        )

        with pytest.raises(approval_service.AgentOperationApprovalError, match='approver_not_allowed'):
            approval_service.confirm_operation(
                db,
                approval.id,
                approver_user_id=8,
                allowed_user_ids={7},
            )

        confirmed = approval_service.confirm_operation(
            db,
            approval.id,
            approver_user_id=7,
            allowed_user_ids={7},
            confirmation_text='确认发布预览',
        )

        assert confirmed.status == 'confirmed'
        assert confirmed.approver_user_id == 7
        assert confirmed.preview_payload['payload']['report_id'] == 18
        assert confirmed.result_payload['confirmation_text'] == '确认发布预览'
        assert confirmed.result_payload['actual_write'] is False
    finally:
        db.close()


def test_execute_confirmed_operation_defaults_to_dry_run_without_executor_call() -> None:
    db = _db_session()
    executor_calls = []
    try:
        _management_channel(db)
        approval = approval_service.request_operation_preview(
            db,
            operation_type='supplement_production',
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            preview_payload={'business_date': '2026-06-13', 'tons': 12.5},
        )
        approval_service.confirm_operation(db, approval.id, approver_user_id=7, allowed_user_ids={7})

        executed = approval_service.execute_confirmed_operation(
            db,
            approval.id,
            executor=lambda payload: executor_calls.append(payload) or {'ok': True},
        )

        assert executed.status == 'dry_run_executed'
        assert executor_calls == []
        assert executed.result_payload['execution_mode'] == 'dry_run'
        assert executed.result_payload['actual_write'] is False
    finally:
        db.close()


def test_execute_confirmed_operation_requires_explicit_executor_for_real_run() -> None:
    db = _db_session()
    try:
        _management_channel(db)
        approval = approval_service.request_operation_preview(
            db,
            operation_type='publish_daily_report',
            requester_user_id=7,
            channel_key='management-chat',
            allowed_user_ids={7},
            preview_payload={'business_date': '2026-06-13', 'report_id': 18},
        )
        approval_service.confirm_operation(db, approval.id, approver_user_id=7, allowed_user_ids={7})

        with pytest.raises(approval_service.AgentOperationApprovalError, match='executor_required'):
            approval_service.execute_confirmed_operation(db, approval.id, dry_run=False)
    finally:
        db.close()
