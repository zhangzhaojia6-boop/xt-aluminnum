from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash, verify_password
from app.core.deps import get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop, WorkshopTemplateConfig
from app.models.system import AuditLog, User


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'qr-login.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkshopTemplateConfig.__table__,
            User.__table__,
            Equipment.__table__,
            AuditLog.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)


def _override_db(session_factory) -> None:
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _seed_machine(session_factory, *, status: str = 'running', bound: bool = True):
    with session_factory() as db:
        workshop = Workshop(code='ZR2', name='铸二车间', sort_order=2, is_active=True)
        db.add(workshop)
        db.flush()
        user = None
        if bound:
            user = User(
                username='ZR2-3',
                password_hash=get_password_hash('384756'),
                pin_code='384756',
                name='铸二车间 3#机',
                role='shift_leader',
                workshop_id=workshop.id,
                data_scope_type='self_workshop',
                is_mobile_user=True,
                is_active=status == 'running',
            )
            db.add(user)
            db.flush()
        equipment = Equipment(
            code='ZR2-3',
            name='3#机',
            workshop_id=workshop.id,
            equipment_type='cast_roller',
            operational_status=status,
            shift_mode='three',
            assigned_shift_ids=[1, 2, 3],
            qr_code='XT-ZR2-3',
            bound_user_id=user.id if user else None,
            is_active=True,
        )
        db.add(equipment)
        db.commit()


def _seed_workshop_qr(session_factory) -> None:
    with session_factory() as db:
        workshop = Workshop(code='LW', name='冷轧车间', sort_order=3, is_active=True)
        db.add(workshop)
        db.flush()
        db.add(
            Equipment(
                code='LW-WORKSHOP',
                name='冷轧车间码',
                workshop_id=workshop.id,
                equipment_type='virtual_workshop_qr',
                operational_status='running',
                qr_code='XT-LW-WORKSHOP',
                is_active=True,
            )
        )
        db.commit()


def _seed_role_qr(
    session_factory,
    *,
    code: str,
    qr_code: str,
    workshop: bool = True,
    existing_user: bool = False,
    workshop_code: str = 'LW',
    workshop_name: str = '冷轧车间',
) -> int | None:
    with session_factory() as db:
        workshop_id = 999
        if workshop:
            workshop_row = Workshop(code=workshop_code, name=workshop_name, sort_order=3, is_active=True)
            db.add(workshop_row)
            db.flush()
            workshop_id = workshop_row.id

        user_id = None
        if existing_user:
            user = User(
                username=code.upper(),
                password_hash=get_password_hash('Existing#Pass2026'),
                name='冷轧电工',
                role='energy_stat',
                workshop_id=workshop_id,
                is_active=True,
                is_mobile_user=True,
            )
            db.add(user)
            db.flush()
            user_id = user.id

        db.add(
            Equipment(
                code=code,
                name=f'{code} 角色码',
                workshop_id=workshop_id,
                equipment_type='virtual_role_qr',
                operational_status='running',
                qr_code=qr_code,
                is_active=True,
            )
        )
        db.commit()
        return user_id


def test_qr_login_returns_token_and_machine_info(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_machine(session_factory, status='running', bound=True)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    client = TestClient(app)
    try:
        response = client.post('/api/v1/auth/qr-login', json={'qr_code': 'XT-ZR2-3'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['access_token']
    assert payload['user']['username'] == 'ZR2-3'
    assert payload['machine_info'] == {
        'machine_id': 1,
        'machine_code': 'ZR2-3',
        'machine_name': '3#机',
        'workshop_id': 1,
        'workshop_name': '铸二车间',
        'qr_code': 'XT-ZR2-3',
    }


def test_qr_login_rejects_stopped_machine(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_machine(session_factory, status='stopped', bound=True)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    client = TestClient(app)
    try:
        response = client.post('/api/v1/auth/qr-login', json={'qr_code': 'XT-ZR2-3'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()['detail'] == '该机台已停机'


def test_qr_login_rejects_unbound_machine(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_machine(session_factory, status='running', bound=False)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    client = TestClient(app)
    try:
        response = client.post('/api/v1/auth/qr-login', json={'qr_code': 'XT-ZR2-3'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()['detail'] == '该机台未绑定账号，请联系管理员'


def test_qr_login_virtual_workshop_redirects_to_workshop(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_workshop_qr(session_factory)
    _override_db(session_factory)

    response = TestClient(app).post('/api/v1/auth/qr-login', json={'qr_code': 'XT-LW-WORKSHOP'})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        'type': 'workshop_redirect',
        'workshop_code': 'LW',
        'workshop_name': '冷轧车间',
    }
    assert 'access_token' not in payload


def test_qr_login_virtual_role_creates_mobile_operator_user(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_role_qr(session_factory, code='LW-OP', qr_code='XT-LW-OP')
    _override_db(session_factory)

    response = TestClient(app).post('/api/v1/auth/qr-login', json={'qr_code': 'XT-LW-OP'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['access_token']
    assert payload['token_type'] == 'bearer'
    assert payload['user']['username'] == 'LW-OP'
    assert payload['user']['role'] == 'machine_operator'
    assert payload['user']['workshop_id'] == 1
    assert payload['user']['is_mobile_user'] is True
    assert payload['machine_info'] == {
        'machine_id': 1,
        'machine_code': 'LW-OP',
        'machine_name': 'LW-OP 角色码',
        'workshop_id': 1,
        'workshop_name': '冷轧车间',
        'qr_code': 'XT-LW-OP',
    }

    with session_factory() as db:
        user = db.query(User).filter(User.username == 'LW-OP').one()
        assert user.role == 'machine_operator'
        assert user.is_mobile_user is True
        assert verify_password('xt123456', user.password_hash) is False
        assert user.pin_code is None
        audit = db.query(AuditLog).filter(AuditLog.action == 'qr_login').one()
        assert audit.user_id == user.id
        assert audit.table_name == 'equipment'


def test_qr_login_virtual_role_reuses_existing_user(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    existing_user_id = _seed_role_qr(
        session_factory,
        code='LW-EN',
        qr_code='XT-LW-EN',
        existing_user=True,
    )
    _override_db(session_factory)

    response = TestClient(app).post('/api/v1/auth/qr-login', json={'qr_code': 'XT-LW-EN'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['user']['id'] == existing_user_id
    assert payload['user']['username'] == 'LW-EN'
    assert payload['user']['role'] == 'energy_stat'
    assert payload['machine_info'] is None

    with session_factory() as db:
        assert db.query(User).filter(User.username == 'LW-EN').count() == 1


def test_qr_login_virtual_role_rejects_missing_workshop(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_role_qr(session_factory, code='LW-HY', qr_code='XT-LW-HY', workshop=False)
    _override_db(session_factory)

    response = TestClient(app).post('/api/v1/auth/qr-login', json={'qr_code': 'XT-LW-HY'})

    assert response.status_code == 404
    assert response.json()['detail'] == '车间不存在'


def test_qr_login_virtual_role_rejects_invalid_role_suffix(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_role_qr(session_factory, code='LW-XX', qr_code='XT-LW-XX')
    _override_db(session_factory)

    response = TestClient(app).post('/api/v1/auth/qr-login', json={'qr_code': 'XT-LW-XX'})

    assert response.status_code == 400
    assert response.json()['detail'] == '无效角色码'


@pytest.mark.parametrize(
    ('code', 'qr_code', 'expected_role', 'expected_mode', 'expected_submit_target'),
    [
        ('ZR2-EN', 'XT-ZR2-EN', 'energy_stat', 'per_shift', 'shift_report'),
        ('ZR2-CS', 'XT-ZR2-CS', 'consumable_stat', 'per_shift', 'shift_report'),
        ('ZR2-1-OP', 'XT-ZR2-1-OP', 'machine_operator', 'per_coil', 'coil_entry'),
    ],
)
def test_qr_role_login_can_fetch_mobile_entry_fields_with_testclient(
    tmp_path,
    *,
    code: str,
    qr_code: str,
    expected_role: str,
    expected_mode: str,
    expected_submit_target: str,
) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_role_qr(
        session_factory,
        code=code,
        qr_code=qr_code,
        workshop_code='ZR2',
        workshop_name='铸二车间',
    )
    _override_db(session_factory)

    client = TestClient(app)
    login_response = client.post('/api/v1/auth/qr-login', json={'qr_code': qr_code})
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload['access_token']
    assert login_payload['user']['role'] == expected_role

    fields_response = client.get(
        '/api/v1/mobile/entry-fields',
        headers={'Authorization': f"Bearer {login_payload['access_token']}"},
    )

    assert fields_response.status_code == 200
    fields_payload = fields_response.json()
    assert fields_payload['mode'] == expected_mode
    assert fields_payload['submit_target'] == expected_submit_target
    assert isinstance(fields_payload['groups'], list)
    assert fields_payload['groups']
    assert all(isinstance(group.get('fields'), list) for group in fields_payload['groups'])
    assert fields_payload['groups'][0]['fields']
    if expected_role == 'consumable_stat':
        first_group_field_names = {f['name'] for f in fields_payload['groups'][0]['fields']}
        assert 'liquefied_gas_per_ton' in first_group_field_names
    if expected_role == 'machine_operator':
        assert fields_payload['identity_field'] == 'tracking_card_no'
        first_group_fields = fields_payload['groups'][0]['fields']
        assert first_group_fields[0]['name'] == 'tracking_card_no'
        assert len(fields_payload['groups']) == 1
        all_field_names = {
            f['name']
            for group in fields_payload['groups']
            for f in group['fields']
        }
        assert 'liquefied_gas_per_ton' not in all_field_names
        assert 'titanium_wire_per_ton' not in all_field_names
        assert 'paper_furnace' not in all_field_names
        assert 'static_furnace' not in all_field_names
        assert 'unit_output' not in all_field_names
        assert 'gas_consumption' not in all_field_names
    else:
        assert fields_payload['identity_field'] is None


def test_qr_role_login_can_fetch_current_shift_with_testclient(tmp_path, monkeypatch) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_role_qr(
        session_factory,
        code='ZR2-EN',
        qr_code='XT-ZR2-EN',
        workshop_code='ZR2',
        workshop_name='铸二车间',
    )
    _override_db(session_factory)

    def fake_current_shift(_db, *, current_user):
        assert current_user.username == 'ZR2-EN'
        assert current_user.role == 'energy_stat'
        return {
            'business_date': date(2026, 5, 6),
            'shift_id': None,
            'shift_code': None,
            'shift_name': None,
            'workshop_id': current_user.workshop_id,
            'workshop_code': 'ZR2',
            'workshop_name': '铸二车间',
            'workshop_type': 'casting',
            'machine_id': None,
            'machine_code': None,
            'machine_name': None,
            'is_machine_bound': False,
            'machine_custom_fields': [],
            'team_id': None,
            'team_name': None,
            'leader_name': current_user.name,
            'report_id': None,
            'report_status': 'unreported',
            'entry_channel': 'qr_role',
            'dingtalk_ready': False,
            'dingtalk_hint': None,
            'ownership_note': None,
            'active_reminders': [],
            'attendance_confirmation_id': None,
            'attendance_machine_id': None,
            'attendance_machine_name': None,
            'attendance_status': 'not_started',
            'attendance_exception_count': 0,
            'attendance_pending_count': 0,
            'can_submit': True,
        }

    monkeypatch.setattr('app.routers.mobile.mobile_report_service.get_current_shift', fake_current_shift)

    client = TestClient(app)
    login_response = client.post('/api/v1/auth/qr-login', json={'qr_code': 'XT-ZR2-EN'})
    assert login_response.status_code == 200
    token = login_response.json()['access_token']

    shift_response = client.get(
        '/api/v1/mobile/current-shift',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert shift_response.status_code == 200
    payload = shift_response.json()
    assert payload['business_date'] == '2026-05-06'
    assert payload['workshop_code'] == 'ZR2'
    assert payload['leader_name'] == 'ZR2-EN 角色码'
    assert payload['entry_channel'] == 'qr_role'
    assert payload['can_submit'] is True
