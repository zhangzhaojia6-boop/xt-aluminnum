from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash
from app.core.deps import get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop
from app.models.system import AuditLog, User


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'qr-login.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, User.__table__, Equipment.__table__, AuditLog.__table__])
    return sessionmaker(bind=engine, future=True)


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
