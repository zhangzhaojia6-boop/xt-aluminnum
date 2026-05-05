from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.main import app
from app.routers import notifications


def _override_user(user_id: int) -> None:
    def _user():
        return SimpleNamespace(id=user_id, role='manager', is_active=True)

    app.dependency_overrides[get_current_user] = _user


def teardown_function() -> None:
    app.dependency_overrides.clear()
    notifications.notification_read_state.clear()


def test_notification_read_state_is_isolated_per_user() -> None:
    client = TestClient(app)

    _override_user(1)
    marked = client.post('/api/v1/notifications/welcome/read')
    assert marked.status_code == 200
    assert marked.json() == {'ok': True}
    user_one_unread = client.get('/api/v1/notifications/unread-count')
    assert user_one_unread.status_code == 200
    assert user_one_unread.json() == {'count': 0}

    _override_user(2)
    user_two_unread = client.get('/api/v1/notifications/unread-count')
    assert user_two_unread.status_code == 200
    assert user_two_unread.json() == {'count': 1}
    user_two_notifications = client.get('/api/v1/notifications')
    assert user_two_notifications.status_code == 200
    assert user_two_notifications.json()[0]['read'] is False

    _override_user(1)
    user_one_notifications = client.get('/api/v1/notifications')
    assert user_one_notifications.status_code == 200
    assert user_one_notifications.json()[0]['read'] is True


def test_mark_read_returns_404_for_missing_notification() -> None:
    _override_user(1)

    response = TestClient(app).post('/api/v1/notifications/missing/read')

    assert response.status_code == 404
    assert response.json()['detail'] == '通知不存在'
