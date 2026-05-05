from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.main import app


def _override_user() -> None:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        role='manager',
        is_active=True,
    )


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_search_returns_matching_navigation_item() -> None:
    _override_user()

    response = TestClient(app).get('/api/v1/search', params={'q': 'AI'})

    assert response.status_code == 200
    assert response.json()['navigation'] == [
        {'title': 'AI 工作台', 'path': '/manage/ai', 'group': 'manage'},
    ]


def test_search_rejects_blank_query_after_strip() -> None:
    _override_user()

    response = TestClient(app).get('/api/v1/search', params={'q': '   '})

    assert response.status_code == 422
