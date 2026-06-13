from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models import Base
from app.models.system import User


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'agent-management.db'}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _user(role: str) -> User:
    return User(
        id=1,
        username=f'{role}_user',
        password_hash='test',
        name='测试用户',
        role=role,
        data_scope_type='all' if role == 'admin' else 'self_workshop',
        is_active=True,
    )


def _client(session_factory, current_user: User | None):
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_agent_management_overview_route_allows_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('admin'))
    try:
        response = client.get('/api/v1/agent-management/overview')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['safe_mode'] is True
    assert payload['summary']['agent_total'] == 0
    assert payload['summary']['knowledge_entry_total'] >= 1
    assert payload['knowledge_entries']


def test_agent_management_overview_route_rejects_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.get('/api/v1/agent-management/overview')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()['detail'] == 'Agent management access denied'


def test_agent_management_overview_route_requires_login(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, None)
    try:
        response = client.get('/api/v1/agent-management/overview')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_agent_management_knowledge_routes_answer_with_sources_for_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('admin'))
    try:
        list_response = client.get('/api/v1/agent-management/knowledge')
        answer_response = client.post(
            '/api/v1/agent-management/knowledge/answer',
            json={'question': '全厂总产量和MES包装产量是什么关系？'},
        )
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()['total'] >= 1
    assert answer_response.status_code == 200
    payload = answer_response.json()
    assert payload['can_answer'] is True
    assert payload['citations']
    assert '实时数值' not in payload['answer']


def test_agent_management_knowledge_routes_reject_non_admin(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client(session_factory, _user('manager'))
    try:
        response = client.get('/api/v1/agent-management/knowledge')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
