from __future__ import annotations

from types import SimpleNamespace


from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.assistant import AiBriefingEvent, AiContextPack, AiConversation, AiMessage, AiWatchlistItem
from app.routers import ai, notifications


def _build_ai_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'platform-ai.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            AiConversation.__table__,
            AiMessage.__table__,
            AiContextPack.__table__,
            AiBriefingEvent.__table__,
            AiWatchlistItem.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def _override_db(db):
    def _dependency():
        yield db

    return _dependency


def _override_user() -> None:
    def _user():
        return SimpleNamespace(id=1, role='manager', is_active=True)

    app.dependency_overrides[get_current_user] = _user


def teardown_function() -> None:
    app.dependency_overrides.clear()
    ai.conversations_db.clear()
    for notification in notifications.notifications_db:
        notification['read'] = False


def test_ai_conversation_and_chat_stream_routes(tmp_path) -> None:
    db = _build_ai_session(tmp_path)
    _override_user()
    app.dependency_overrides[get_db] = _override_db(db)

    try:
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
        assert db.query(AiMessage).count() == 2
    finally:
        db.close()


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
