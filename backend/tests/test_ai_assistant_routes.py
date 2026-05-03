from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.assistant import AiBriefingEvent, AiContextPack, AiConversation, AiMessage, AiWatchlistItem
from app.routers import ai


def _manager_user():
    return SimpleNamespace(id=7, role='manager', is_admin=False, is_manager=True, data_scope_type='all')


def _fake_db():
    yield SimpleNamespace()


def _override_db(db):
    def _dependency():
        yield db

    return _dependency


def _build_ai_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ai-assistant-routes.db'}", future=True)
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


def test_assistant_routes_persist_conversations_and_messages(tmp_path, monkeypatch):
    db = _build_ai_session(tmp_path)
    app.dependency_overrides[get_current_user] = _manager_user
    app.dependency_overrides[get_db] = _override_db(db)
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

    try:
        client = TestClient(app)
        created = client.post('/api/v1/ai/assistant/conversations', json={'title': '数据库对话'})
        assert created.status_code == 200
        conversation_id = created.json()['id']

        assert db.query(AiConversation).count() == 1
        assert db.query(AiConversation).first().public_id == conversation_id

        sent = client.post(
            f'/api/v1/ai/assistant/conversations/{conversation_id}/messages',
            json={'content': '冷轧 1# 怎么了？', 'scope': {'type': 'machine', 'key': '冷轧:01'}},
        )

        assert sent.status_code == 200
        assert db.query(AiMessage).count() == 2
        assert client.get(f'/api/v1/ai/assistant/conversations/{conversation_id}/messages').json()[0]['content'] == '冷轧 1# 怎么了？'
    finally:
        db.close()


def test_assistant_factory_context_rejects_non_manager(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=9,
        role='mobile',
        is_admin=False,
        is_manager=False,
        is_reviewer=False,
        data_scope_type='self_workshop',
    )
    monkeypatch.setattr('app.routers.ai.ai_context_service.answer_from_context', lambda *args, **kwargs: {})

    response = TestClient(app).post('/api/v1/ai/assistant/ask', json={'question': '全厂状态？'})

    assert response.status_code == 403


def test_assistant_factory_context_allows_scope_summary_reviewer_role(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=10,
        role='statistician',
        is_admin=False,
        is_manager=False,
        is_reviewer=False,
        workshop_id=1,
        team_id=None,
        data_scope_type='self_workshop',
        assigned_shift_ids=[],
    )
    monkeypatch.setattr(
        'app.routers.ai.ai_context_service.answer_from_context',
        lambda *args, **kwargs: {
            'answer': 'scope ok',
            'confidence': 'high',
            'evidence_refs': [],
            'missing_data': [],
            'recommended_next_actions': [],
            'can_create_watch': True,
        },
    )

    response = TestClient(app).post('/api/v1/ai/assistant/ask', json={'question': '车间状态？'})

    assert response.status_code == 200
    assert response.json()['answer'] == 'scope ok'


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


def test_briefing_and_watchlist_routes_persist_database(tmp_path, monkeypatch):
    db = _build_ai_session(tmp_path)
    app.dependency_overrides[get_current_user] = _manager_user
    app.dependency_overrides[get_db] = _override_db(db)

    def fake_generate_briefing(session, *args, **kwargs):
        event = AiBriefingEvent(
            public_id='brief-db',
            owner_user_id=kwargs.get('owner_user_id'),
            briefing_type='opening_shift',
            severity='warning',
            title='开班简报',
            payload={'rules_fired': []},
            read=False,
            follow_up_status='none',
        )
        session.add(event)
        session.flush()
        return {
            'id': 'brief-db',
            'briefing_type': 'opening_shift',
            'severity': 'warning',
            'title': '开班简报',
            'payload': {'rules_fired': []},
            'read': False,
            'follow_up_status': 'none',
        }

    monkeypatch.setattr('app.routers.ai.ai_briefing_service.generate_briefing', fake_generate_briefing)

    try:
        client = TestClient(app)
        generated = client.post('/api/v1/ai/briefings/generate-now', json={'briefing_type': 'opening_shift'})
        assert generated.status_code == 200
        assert db.query(AiBriefingEvent).count() == 1
        assert db.query(AiBriefingEvent).first().owner_user_id == 7

        assert client.get('/api/v1/ai/briefings').json()[0]['id'] == 'brief-db'
        assert client.post('/api/v1/ai/briefings/brief-db/read').json()['read'] is True
        assert db.query(AiBriefingEvent).first().read is True

        created_watch = client.post(
            '/api/v1/ai/watchlist',
            json={'watch_type': 'machine', 'scope_key': '冷轧:01'},
        )
        assert created_watch.status_code == 200
        watch_id = created_watch.json()['id']
        assert db.query(AiWatchlistItem).count() == 1
        assert client.patch(f'/api/v1/ai/watchlist/{watch_id}', json={'active': False}).json()['active'] is False
        assert db.query(AiWatchlistItem).first().active is False
        assert client.delete(f'/api/v1/ai/watchlist/{watch_id}').status_code == 200
        assert db.query(AiWatchlistItem).count() == 0
    finally:
        db.close()


def test_briefing_routes_filter_by_owner(tmp_path):
    db = _build_ai_session(tmp_path)
    db.add_all(
        [
            AiBriefingEvent(
                public_id='brief-own',
                owner_user_id=7,
                briefing_type='opening_shift',
                severity='warning',
                title='开班简报',
                payload={'rules_fired': []},
            ),
            AiBriefingEvent(
                public_id='brief-other',
                owner_user_id=8,
                briefing_type='opening_shift',
                severity='warning',
                title='其他汇报',
                payload={'rules_fired': []},
            ),
        ]
    )
    db.commit()
    app.dependency_overrides[get_current_user] = _manager_user
    app.dependency_overrides[get_db] = _override_db(db)

    try:
        client = TestClient(app)

        listed = client.get('/api/v1/ai/briefings')
        assert listed.status_code == 200
        assert [item['id'] for item in listed.json()] == ['brief-own']

        assert client.post('/api/v1/ai/briefings/brief-other/read').status_code == 404
        assert db.query(AiBriefingEvent).filter(AiBriefingEvent.public_id == 'brief-other').first().read is False
    finally:
        db.close()
