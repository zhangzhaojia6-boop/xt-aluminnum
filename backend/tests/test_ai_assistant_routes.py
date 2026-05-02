from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.routers import ai


def _manager_user():
    return SimpleNamespace(id=7, role='manager', is_admin=False, is_manager=True, data_scope_type='all')


def _fake_db():
    yield SimpleNamespace()


def teardown_function() -> None:
    app.dependency_overrides.clear()
    ai.conversations_db.clear()
    ai.briefings_db.clear()
    ai.watchlist_db.clear()


def test_assistant_conversation_routes_and_compatibility(monkeypatch):
    app.dependency_overrides[get_current_user] = _manager_user
    app.dependency_overrides[get_db] = _fake_db
    monkeypatch.setattr(
        'app.routers.ai.ai_context_service.answer_from_context',
        lambda *args, **kwargs: {
            'answer': '当前冷轧 1# 有 1 条停滞卷。',
            'confidence': 'high',
            'evidence_refs': [{'kind': 'machine', 'key': '冷轧:01'}],
            'missing_data': [],
            'recommended_next_actions': ['查看卷级追踪'],
            'can_create_watch': True,
        },
    )

    client = TestClient(app)
    created = client.post('/api/v1/ai/assistant/conversations', json={'title': '工厂问答'})
    assert created.status_code == 200
    conversation_id = created.json()['id']

    listed = client.get('/api/v1/ai/assistant/conversations')
    assert listed.status_code == 200
    assert listed.json()[0]['id'] == conversation_id

    sent = client.post(
        f'/api/v1/ai/assistant/conversations/{conversation_id}/messages',
        json={'content': '冷轧 1# 怎么了？', 'scope': {'type': 'machine', 'key': '冷轧:01'}},
    )
    assert sent.status_code == 200
    assert sent.json()['answer']['confidence'] == 'high'

    messages = client.get(f'/api/v1/ai/assistant/conversations/{conversation_id}/messages')
    assert messages.status_code == 200
    assert messages.json()[0]['content'] == '冷轧 1# 怎么了？'

    asked = client.post('/api/v1/ai/assistant/ask', json={'question': '全厂状态？', 'scope': {'type': 'factory', 'key': 'all'}})
    assert asked.status_code == 200
    assert asked.json()['can_create_watch'] is True

    compatible = client.post('/api/v1/ai/conversations')
    assert compatible.status_code == 200


def test_briefing_and_watchlist_routes(monkeypatch):
    app.dependency_overrides[get_current_user] = _manager_user
    app.dependency_overrides[get_db] = _fake_db
    monkeypatch.setattr(
        'app.routers.ai.ai_briefing_service.generate_briefing',
        lambda *args, **kwargs: {
            'id': 'brief-1',
            'briefing_type': 'opening_shift',
            'severity': 'warning',
            'title': '开班简报',
            'payload': {'rules_fired': []},
            'read': False,
            'follow_up_status': 'none',
        },
    )

    client = TestClient(app)
    generated = client.post('/api/v1/ai/briefings/generate-now', json={'briefing_type': 'opening_shift'})
    assert generated.status_code == 200
    briefing_id = generated.json()['id']

    listed = client.get('/api/v1/ai/briefings')
    assert listed.status_code == 200
    assert listed.json()[0]['id'] == briefing_id

    assert client.post(f'/api/v1/ai/briefings/{briefing_id}/read').status_code == 200
    assert client.post(f'/api/v1/ai/briefings/{briefing_id}/follow-up').status_code == 200

    created_watch = client.post(
        '/api/v1/ai/watchlist',
        json={
            'watch_type': 'machine',
            'scope_key': '冷轧:01',
            'trigger_rules': ['delay_hours_high'],
            'quiet_hours': {'start': '22:00', 'end': '07:00'},
            'frequency': 'hourly',
            'channels': ['in_app'],
            'active': True,
        },
    )
    assert created_watch.status_code == 200
    watch_id = created_watch.json()['id']

    assert client.get('/api/v1/ai/watchlist').json()[0]['id'] == watch_id
    assert client.patch(f'/api/v1/ai/watchlist/{watch_id}', json={'active': False}).json()['active'] is False
    assert client.delete(f'/api/v1/ai/watchlist/{watch_id}').status_code == 200
