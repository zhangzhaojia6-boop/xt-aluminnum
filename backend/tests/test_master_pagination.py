from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.master import Employee, Workshop
from app.models.system import User


class _FakeQuery:
    def __init__(self, items):
        self._items = list(items)
        self._skip = 0
        self._limit = None

    def order_by(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def count(self):
        return len(self._items)

    def offset(self, skip: int):
        self._skip = skip
        return self

    def limit(self, limit: int):
        self._limit = limit
        return self

    def all(self):
        items = self._items[self._skip :]
        if self._limit is not None:
            items = items[: self._limit]
        return items


class _FakeDB:
    def __init__(self, mapping):
        self._mapping = mapping

    def query(self, model):
        return _FakeQuery(self._mapping[model])


def test_list_employees_returns_paginated_payload() -> None:
    employees = [
        SimpleNamespace(
            id=index,
            employee_no=f'E{index:03d}',
            name=f'Employee {index}',
            workshop_id=1,
            team_id=None,
            position_id=None,
            phone=None,
            dingtalk_user_id=None,
            hire_date=None,
            is_active=True,
        )
        for index in range(1, 151)
    ]

    def fake_get_db():
        yield _FakeDB({Employee: employees})

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    response = client.get('/api/v1/master/employees')

    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 150
    assert payload['skip'] == 0
    assert payload['limit'] == 100
    assert len(payload['items']) == 100
    assert payload['items'][0]['employee_no'] == 'E001'

    app.dependency_overrides.clear()


def test_list_workshops_excludes_inactive_records(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'master-workshops.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True)

    with SessionLocal() as db:
        db.add_all(
            [
                Workshop(code='ACTIVE', name='有效车间', sort_order=1, is_active=True),
                Workshop(code='INACTIVE', name='停用车间', sort_order=2, is_active=False),
            ]
        )
        db.commit()

    def fake_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    response = client.get('/api/v1/master/workshops')

    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 1
    assert [item['code'] for item in payload['items']] == ['ACTIVE']

    app.dependency_overrides.clear()
