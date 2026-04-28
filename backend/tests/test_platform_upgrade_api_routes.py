from __future__ import annotations

from types import SimpleNamespace


from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.main import app
from app.routers import ai, notifications


def _override_user() -> None:
    def _user():
        return SimpleNamespace(id=1, role='manager', is_active=True)

    app.dependency_overrides[get_current_user] = _user


def teardown_function() -> None:
    app.dependency_overrides.clear()
    ai.conversations_db.clear()
    for notification in notifications.notifications_db:
        notification['read'] = False


def test_ai_conversation_and_chat_stream_routes() -> None:
    _override_user()
    client = TestClient(app)

    created = client.post('/api/v1/ai/conversations')
    assert created.status_code == 200
    conversation_id = created.json()['id']

    response = client.post('/api/v1/ai/chat', json={'conversation_id': conversation_id, 'message': '测试'})

    assert response.status_code == 200
    assert 'text/event-stream' in response.headers['content-type']
    assert 'data:' in response.text
    detail = client.get(f'/api/v1/ai/conversations/{conversation_id}').json()
    assert detail['messages'][0]['content'] == '测试'


def test_search_export_and_notification_routes() -> None:
    _override_user()
    client = TestClient(app)

    search = client.get('/api/v1/search', params={'q': 'AI'})
    assert search.status_code == 200
    assert search.json()['navigation'][0]['path'] == '/manage/ai'

    exported = client.post('/api/v1/export/overview', json={'format': 'csv'})
    assert exported.status_code == 200
    assert exported.headers['content-disposition'].startswith('attachment;')

    unread = client.get('/api/v1/notifications/unread-count')
    assert unread.status_code == 200
    assert unread.json()['count'] >= 1

    marked = client.post('/api/v1/notifications/welcome/read')
    assert marked.status_code == 200
    assert marked.json() == {'ok': True}
