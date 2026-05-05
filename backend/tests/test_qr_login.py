from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash, verify_password
from app.core.deps import get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop
from app.models.system import AuditLog, User


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'qr-login.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, User.__table__, Equipment.__table__, AuditLog.__table__])
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
) -> int | None:
    with session_factory() as db:
        workshop_id = 999
        if workshop:
            workshop_row = Workshop(code='LW', name='冷轧车间', sort_order=3, is_active=True)
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
