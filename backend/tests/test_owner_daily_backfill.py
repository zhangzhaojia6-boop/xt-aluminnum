from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.agent_communication import AgentEvent
from app.models.master import Team, Workshop
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.reports import DailyFactCorrection
from app.models.system import AuditLog, User
from app.services.machine_fact_gap_service import sync_machine_fact_gap_event
from app.services.mobile_report import summary as mobile_summary


SHANGHAI = ZoneInfo('Asia/Shanghai')
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=SHANGHAI)


def _build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'owner-daily-backfill.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            AuditLog.__table__,
            AgentEvent.__table__,
            DailyFactCorrection.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def _seed_owner(db) -> User:
    workshop = Workshop(
        id=11,
        code='CPK',
        name='成品库',
        workshop_type='inventory',
        sort_order=1,
        is_active=True,
    )
    owner = User(
        id=44,
        username='CPK-EC',
        password_hash='x',
        name='成品库内勤',
        role='storage_owner',
        workshop_id=workshop.id,
        is_mobile_user=True,
        is_active=True,
    )
    db.add_all([workshop, owner])
    db.commit()
    return owner


def _freeze_owner_business_time(monkeypatch) -> None:
    monkeypatch.setattr(mobile_summary, '_local_now', lambda *_args, **_kwargs: NOW)
    monkeypatch.setattr(
        mobile_summary,
        'resolve_owner_daily_business_date',
        lambda *_args, **_kwargs: date(2026, 7, 19),
    )


def test_owner_daily_save_keeps_selected_recent_historical_date(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        _freeze_owner_business_time(monkeypatch)

        payload = mobile_summary.save_owner_daily_entry(
            db,
            payload={'business_date': date(2026, 7, 17), 'data': {'finished_inbound_daily': 85}},
            current_user=owner,
        )

        assert payload['business_date'] == date(2026, 7, 17)
        entry = db.query(WorkOrderEntry).one()
        assert entry.business_date == date(2026, 7, 17)
        assert entry.extra_payload == {'finished_inbound_daily': 85}
        audit = db.query(AuditLog).one()
        assert audit.action == 'owner_daily_historical_create'
        assert audit.reason == 'owner_daily_historical_backfill'
        assert audit.old_value is None
        assert audit.new_value['business_date'] == '2026-07-17'
        assert audit.new_value['data'] == {'finished_inbound_daily': 85}
        assert db.query(DailyFactCorrection).count() == 0
    finally:
        db.close()


def test_owner_daily_assigned_gap_alias_creates_one_verified_correction(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        owner.role = 'quality_owner'
        db.commit()
        _freeze_owner_business_time(monkeypatch)
        event = AgentEvent(
            event_type='daily_fact_gap',
            severity='warning',
            status='open',
            scope_type='factory',
            source_type='daily_fact_closure',
            source_ref='daily_fact_gap:2026-07-17:daily_yield_rate',
            business_date=date(2026, 7, 17),
            payload={
                'field': 'daily_yield_rate',
                'owner_role': 'quality_owner',
                'entry_fields': ['plant_wide_yield_rate'],
                'human_action_required': True,
                'last_checked_trace_id': 'daily-fact-closure:2026-07-17',
            },
        )
        db.add(event)
        db.commit()

        mobile_summary.save_owner_daily_entry(
            db,
            payload={'business_date': date(2026, 7, 17), 'data': {'plant_wide_yield_rate': 84.86}},
            current_user=owner,
        )
        mobile_summary.save_owner_daily_entry(
            db,
            payload={'business_date': date(2026, 7, 17), 'data': {'plant_wide_yield_rate': 85.12}},
            current_user=owner,
        )

        entry = db.query(WorkOrderEntry).one()
        correction = db.query(DailyFactCorrection).one()
        assert correction.field_name == 'daily_yield_rate'
        assert correction.value_payload == {
            'value': 85.12,
            'source_type': 'verified_owner_daily',
            'entry_id': entry.id,
            'event_id': event.id,
            'entry_field': 'plant_wide_yield_rate',
            'owner_role': 'quality_owner',
        }
        assert correction.unit == '%'
        assert correction.actor_user_id == owner.id
        assert correction.trace_id == 'daily-fact-closure:2026-07-17'
        assert correction.status == 'active'
    finally:
        db.close()


def test_planning_owner_wip_gap_submission_creates_traced_verified_correction(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        owner.role = 'planning_owner'
        db.commit()
        _freeze_owner_business_time(monkeypatch)
        event = AgentEvent(
            event_type='daily_fact_gap',
            severity='warning',
            status='open',
            scope_type='factory',
            source_type='daily_fact_closure',
            source_ref='daily_fact_gap:2026-07-17:wip_total',
            business_date=date(2026, 7, 17),
            payload={
                'field': 'wip_total',
                'owner_role': 'planning_owner',
                'entry_fields': ['wip_total'],
                'human_action_required': True,
                'last_checked_trace_id': 'daily-fact-closure:2026-07-17',
            },
        )
        db.add(event)
        db.commit()

        mobile_summary.save_owner_daily_entry(
            db,
            payload={'business_date': date(2026, 7, 17), 'data': {'wip_total': 1189}},
            current_user=owner,
        )

        entry = db.query(WorkOrderEntry).one()
        correction = db.query(DailyFactCorrection).one()
        assert correction.field_name == 'wip_total'
        assert correction.value_payload == {
            'value': 1189,
            'source_type': 'verified_owner_daily',
            'entry_id': entry.id,
            'event_id': event.id,
            'entry_field': 'wip_total',
            'owner_role': 'planning_owner',
        }
        assert correction.unit == '吨'
        assert correction.actor_user_id == owner.id
        assert correction.trace_id == 'daily-fact-closure:2026-07-17'
        assert correction.status == 'active'
    finally:
        db.close()


@pytest.mark.parametrize('requested_date', [date(2026, 7, 11), date(2026, 7, 20)])
def test_owner_daily_save_rejects_dates_outside_seven_day_window(tmp_path, monkeypatch, requested_date) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        _freeze_owner_business_time(monkeypatch)

        with pytest.raises(HTTPException) as exc_info:
            mobile_summary.save_owner_daily_entry(
                db,
                payload={'business_date': requested_date, 'data': {'finished_inbound_daily': 85}},
                current_user=owner,
            )

        assert exc_info.value.status_code == 422
        assert db.query(WorkOrderEntry).count() == 0
    finally:
        db.close()


def test_owner_daily_save_keeps_pre_cutoff_compatibility_for_cached_client(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        morning = datetime(2026, 7, 19, 9, 0, tzinfo=SHANGHAI)
        monkeypatch.setattr(mobile_summary, '_local_now', lambda *_args, **_kwargs: morning)
        monkeypatch.setattr(
            mobile_summary,
            'resolve_owner_daily_business_date',
            lambda *_args, **_kwargs: date(2026, 7, 18),
        )

        payload = mobile_summary.save_owner_daily_entry(
            db,
            payload={'business_date': date(2026, 7, 19), 'data': {'finished_inbound_daily': 85}},
            current_user=owner,
        )

        assert payload['business_date'] == date(2026, 7, 18)
        assert db.query(AuditLog).one().action == 'owner_daily_create'
    finally:
        db.close()


def test_owner_daily_retry_updates_one_row_and_records_old_and_new_values(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        _freeze_owner_business_time(monkeypatch)
        base_payload = {'business_date': date(2026, 7, 17), 'data': {'finished_inbound_daily': 85}}
        mobile_summary.save_owner_daily_entry(db, payload=base_payload, current_user=owner)

        mobile_summary.save_owner_daily_entry(
            db,
            payload={'business_date': date(2026, 7, 17), 'data': {'finished_inbound_daily': 86}},
            current_user=owner,
            ip_address='127.0.0.1',
            user_agent='pytest',
        )

        assert db.query(WorkOrderEntry).count() == 1
        entry = db.query(WorkOrderEntry).one()
        assert entry.extra_payload == {'finished_inbound_daily': 86}
        audits = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
        assert [audit.action for audit in audits] == [
            'owner_daily_historical_create',
            'owner_daily_historical_update',
        ]
        assert audits[1].old_value['data'] == {'finished_inbound_daily': 85}
        assert audits[1].new_value['data'] == {'finished_inbound_daily': 86}
        assert audits[1].ip_address == '127.0.0.1'
        assert audits[1].user_agent == 'pytest'
    finally:
        db.close()


def test_overhaul_owner_machine_stop_submission_resolves_matching_gap(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        owner.role = 'overhaul_owner'
        owner.name = '大修内勤'
        db.commit()
        _freeze_owner_business_time(monkeypatch)
        gap = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 17),
            intent='machine_stop',
            machine_filter='2',
            facts={'stop_count': 0, 'top_stops': []},
            trace_id='trace-machine-owner-gap',
        )
        db.commit()

        payload = mobile_summary.save_owner_daily_entry(
            db,
            payload={
                'business_date': date(2026, 7, 17),
                'data': {
                    'machine_stop_records': [
                        {
                            'workshop_name': '伪造车间',
                            'machine_name': '2号机',
                            'shift_name': '白班',
                            'downtime_minutes': 42,
                            'downtime_reason': '换辊待维修确认',
                        },
                    ],
                },
            },
            current_user=owner,
        )

        db.refresh(gap)
        assert gap.status == 'resolved'
        assert gap.payload['resolution_trace_id'].startswith('owner-daily:')
        assert payload['data']['machine_stop_records'] == [
            {
                'workshop_name': '成品库',
                'machine_name': '2号机',
                'machine_code': '',
                'shift_name': '白班',
                'downtime_minutes': 42,
                'downtime_reason': '换辊待维修确认',
            },
        ]
    finally:
        db.close()


def test_machine_stop_submission_requires_a_reason(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        owner.role = 'overhaul_owner'
        db.commit()
        _freeze_owner_business_time(monkeypatch)

        with pytest.raises(HTTPException) as exc_info:
            mobile_summary.save_owner_daily_entry(
                db,
                payload={
                    'business_date': date(2026, 7, 17),
                    'data': {
                        'machine_stop_records': [
                            {
                                'machine_name': '2号机',
                                'downtime_minutes': 42,
                                'downtime_reason': '',
                            },
                        ],
                    },
                },
                current_user=owner,
            )

        assert exc_info.value.status_code == 422
        assert '缺少原因' in exc_info.value.detail
        assert db.query(WorkOrderEntry).count() == 0
    finally:
        db.close()


def test_machine_stop_submission_rejects_fractional_minutes(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    try:
        owner = _seed_owner(db)
        owner.role = 'overhaul_owner'
        db.commit()
        _freeze_owner_business_time(monkeypatch)

        with pytest.raises(HTTPException) as exc_info:
            mobile_summary.save_owner_daily_entry(
                db,
                payload={
                    'business_date': date(2026, 7, 17),
                    'data': {
                        'machine_stop_records': [
                            {
                                'machine_name': '2号机',
                                'downtime_minutes': 42.5,
                                'downtime_reason': '换辊',
                            },
                        ],
                    },
                },
                current_user=owner,
            )

        assert exc_info.value.status_code == 422
        assert '整数' in exc_info.value.detail
        assert db.query(WorkOrderEntry).count() == 0
    finally:
        db.close()


def test_owner_daily_rows_have_a_unique_partial_index() -> None:
    index = next(
        item
        for item in WorkOrderEntry.__table__.indexes
        if item.name == 'uq_work_order_entries_owner_daily_work_order_date'
    )

    assert index.unique is True
    assert tuple(column.name for column in index.columns) == ('work_order_id', 'business_date', 'entry_type')
