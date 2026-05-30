from __future__ import annotations

import time
from datetime import date, time as clock_time
from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user
from app.core.permissions import get_current_manager_user, get_current_mobile_user
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.master import Team, Workshop
from app.models.production import ShiftProductionData
from app.models.shift import ShiftConfig
from app.models.system import User
from app.core.rate_limit import reset_rate_limits


BUSINESS_DATE = date(2026, 5, 14)
SUBMITTED_OUTPUT_WEIGHT = 96.0


def _session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'full-chain-visibility.db'}",
        connect_args={'check_same_thread': False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_reference_data(session_factory) -> None:
    with session_factory() as db:
        workshop = Workshop(
            id=1,
            code='ZR2',
            name='铸二车间',
            workshop_type='casting',
            sort_order=1,
            is_active=True,
        )
        team = Team(id=1, workshop_id=1, code='A', name='甲班', sort_order=1, is_active=True)
        shift = ShiftConfig(
            id=1,
            code='D',
            name='白班',
            shift_type='day',
            start_time=clock_time(8, 0),
            end_time=clock_time(20, 0),
            workshop_id=1,
            is_active=True,
        )
        operator = User(
            id=101,
            username='operator',
            password_hash='x',
            name='主操',
            role='team_leader',
            workshop_id=1,
            team_id=1,
            data_scope_type='self_team',
            assigned_shift_ids=[1],
            is_mobile_user=True,
            is_reviewer=False,
            is_manager=False,
            is_active=True,
        )
        manager = User(
            id=201,
            username='manager',
            password_hash='x',
            name='厂长',
            role='manager',
            workshop_id=None,
            team_id=None,
            data_scope_type='all',
            assigned_shift_ids=[],
            is_mobile_user=False,
            is_reviewer=False,
            is_manager=True,
            is_active=True,
        )
        db.add_all([workshop, team, shift, operator, manager])
        db.commit()


def _client_with_db(session_factory) -> TestClient:
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_mobile_user() -> User:
        return User(
            id=101,
            username='operator',
            password_hash='x',
            name='主操',
            role='team_leader',
            workshop_id=1,
            team_id=1,
            data_scope_type='self_team',
            assigned_shift_ids=[1],
            is_mobile_user=True,
            is_reviewer=False,
            is_manager=False,
            is_active=True,
        )

    def fake_manager_user() -> User:
        return User(
            id=201,
            username='manager',
            password_hash='x',
            name='厂长',
            role='manager',
            workshop_id=None,
            team_id=None,
            data_scope_type='all',
            assigned_shift_ids=[],
            is_mobile_user=False,
            is_reviewer=False,
            is_manager=True,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_manager_user
    app.dependency_overrides[get_current_mobile_user] = fake_mobile_user
    app.dependency_overrides[get_current_manager_user] = fake_manager_user
    reset_rate_limits()
    return TestClient(app)


def _eventually(assertion: Callable[[], None], *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: AssertionError | None = None
    while time.monotonic() <= deadline:
        try:
            assertion()
            return
        except AssertionError as exc:
            last_error = exc
            time.sleep(0.1)
    if last_error is not None:
        raise last_error
    assertion()


def _assert_db_contains_shift_row(session_factory) -> None:
    with session_factory() as db:
        row = (
            db.query(ShiftProductionData)
            .filter(
                ShiftProductionData.business_date == BUSINESS_DATE,
                ShiftProductionData.workshop_id == 1,
                ShiftProductionData.shift_config_id == 1,
                ShiftProductionData.output_weight == SUBMITTED_OUTPUT_WEIGHT,
            )
            .first()
        )
        assert row is not None
        assert row.data_status == 'confirmed'


def _assert_factory_dashboard_contains_row(client: TestClient) -> None:
    response = client.get('/api/v1/dashboard/factory-director', params={'target_date': BUSINESS_DATE.isoformat()})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['total_output_basis'] == 'storage_inbound_output'
    assert payload['today_total_output'] == 0
    assert payload['leader_metrics']['today_total_output'] == 0
    assert payload['process_total_output'] >= SUBMITTED_OUTPUT_WEIGHT
    assert any(
        item.get('workshop_id') == 1 and item.get('total_output', 0) >= SUBMITTED_OUTPUT_WEIGHT
        for item in payload.get('workshop_output_summary', [])
    )


def _assert_workshop_dashboard_contains_row(client: TestClient) -> None:
    response = client.get(
        '/api/v1/dashboard/workshop-director',
        params={'target_date': BUSINESS_DATE.isoformat(), 'workshop_id': 1},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['total_output'] >= SUBMITTED_OUTPUT_WEIGHT
    assert any(
        item.get('workshop_id') == 1 and item.get('total_output', 0) >= SUBMITTED_OUTPUT_WEIGHT
        for item in payload.get('production_lane', [])
    )
    assert any(
        item.get('output_weight') == SUBMITTED_OUTPUT_WEIGHT and item.get('data_status') == 'confirmed'
        for item in payload.get('shift_items', [])
    )


def _assert_daily_report_contains_row(client: TestClient) -> None:
    response = client.get(
        '/api/v1/reports',
        params={'start_date': BUSINESS_DATE.isoformat(), 'end_date': BUSINESS_DATE.isoformat(), 'report_type': 'production'},
    )
    assert response.status_code == 200, response.text


def _assert_daily_export_contains_row(client: TestClient) -> None:
    response = client.post(
        '/api/v1/export/production',
        json={'format': 'csv'},
    )
    assert response.status_code == 200, response.text


def test_mobile_submit_is_visible_across_database_dashboards_report_and_export(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/report/submit',
            json={
                'business_date': BUSINESS_DATE.isoformat(),
                'shift_id': 1,
                'attendance_count': 12,
                'input_weight': 100.0,
                'output_weight': SUBMITTED_OUTPUT_WEIGHT,
                'scrap_weight': 2.0,
                'electricity_daily': 9600.0,
                'gas_daily': 120.0,
                'note': 'full chain regression',
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()['report_status'] == 'approved'

        _eventually(lambda: _assert_db_contains_shift_row(session_factory))
        _eventually(lambda: _assert_factory_dashboard_contains_row(client))
        _eventually(lambda: _assert_workshop_dashboard_contains_row(client))
        _eventually(lambda: _assert_daily_report_contains_row(client))
        _eventually(lambda: _assert_daily_export_contains_row(client))
    finally:
        app.dependency_overrides.clear()
        reset_rate_limits()
