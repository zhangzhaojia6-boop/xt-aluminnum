import asyncio
from datetime import date

from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.deps import get_db
from app.main import app
from app.models.system import User
from app.routers import realtime


class DummyQuery:
    def __init__(self, user: User):
        self.user = user

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.user


class DummyDB:
    def __init__(self, user: User):
        self.user = user

    def query(self, *_args, **_kwargs):
        return DummyQuery(self.user)


def test_realtime_routes_are_registered() -> None:
    assert app.url_path_for('realtime-stream') == '/api/v1/realtime/stream'
    assert app.url_path_for('live-aggregation') == '/api/v1/aggregation/live'
    assert app.url_path_for('live-aggregation-detail') == '/api/v1/aggregation/live/detail'


def test_realtime_stream_filters_events_by_scope(monkeypatch) -> None:
    class DummyRequest:
        async def is_disconnected(self):
            return False

    async def fake_listen(*, after_event_id, limit, timeout=None):
        assert limit == 50
        if after_event_id == 0:
            return [
                {
                    'id': 1,
                    'event_type': 'entry_submitted',
                    'payload': {
                        'tracking_card_no': 'RA240001',
                        'workshop_id': 2,
                        'workshop': '鐑涧杞﹂棿',
                        'machine': '1#',
                        'shift': '鐧界彮',
                        'yield_rate': 97.2,
                    },
                },
                {
                    'id': 2,
                    'event_type': 'entry_submitted',
                    'payload': {
                        'tracking_card_no': 'RA240002',
                        'workshop_id': 3,
                        'workshop': '绮炬暣杞﹂棿',
                        'machine': '2#',
                        'shift': '鐧界彮',
                        'yield_rate': 96.1,
                    },
                },
            ]
        return []

    monkeypatch.setattr('app.routers.realtime.event_bus.listen', fake_listen)

    async def scenario():
        generator = realtime._event_stream(DummyRequest(), workshop_scope=2, cursor=0)
        try:
            return [await anext(generator), await anext(generator)]
        finally:
            await generator.aclose()

    outputs = asyncio.run(scenario())
    body = '\n'.join(outputs)
    assert 'entry_submitted' in body
    assert 'RA240001' in body
    assert 'RA240002' not in body


def test_realtime_event_stream_keeps_running_for_follow_up_events_and_heartbeats(monkeypatch) -> None:
    calls = []

    class DummyRequest:
        async def is_disconnected(self):
            return False

    async def fake_listen(*, after_event_id, limit, timeout=None):
        calls.append((after_event_id, timeout))
        if len(calls) == 1:
            return [
                {
                    'id': 1,
                    'event_type': 'entry_submitted',
                    'payload': {'tracking_card_no': 'RA240001', 'workshop_id': 2},
                }
            ]
        if len(calls) == 2:
            return [
                {
                    'id': 2,
                    'event_type': 'entry_verified',
                    'payload': {'tracking_card_no': 'RA240001', 'workshop_id': 2},
                }
            ]
        return []

    monotonic_values = iter([0.0, 0.0, 0.1, 0.2, 15.3, 15.3, 15.4, 15.5])

    monkeypatch.setattr('app.routers.realtime.event_bus.listen', fake_listen)
    monkeypatch.setattr('app.routers.realtime._monotonic', lambda: next(monotonic_values))

    async def scenario():
        generator = realtime._event_stream(DummyRequest(), workshop_scope=2, cursor=0)
        try:
            return [
                await anext(generator),
                await anext(generator),
                await anext(generator),
                await anext(generator),
            ]
        finally:
            await generator.aclose()

    outputs = asyncio.run(scenario())

    assert outputs[0] == 'retry: 1000\n\n'
    assert 'entry_submitted' in outputs[1]
    assert 'entry_verified' in outputs[2]
    assert outputs[3] == ': heartbeat\n\n'
    assert calls[0] == (0, 0)
    assert calls[1][0] == 1
    assert calls[2][0] == 2


def test_live_aggregation_endpoint_calls_service(monkeypatch) -> None:
    current_user = User(
        id=7,
        username='chief-stat',
        password_hash='x',
        name='Chief Stat',
        role='statistician',
        data_scope_type='all',
        is_active=True,
    )

    def fake_get_db():
        yield DummyDB(current_user)

    def fake_build_live_aggregation(db, *, business_date, workshop_id, current_user):
        assert business_date == date(2026, 3, 27)
        assert workshop_id == 2
        assert current_user.id == 7
        return {
            'business_date': '2026-03-27',
            'overall_progress': {'submitted_cells': 4, 'total_cells': 9},
            'workshops': [
                {
                    'workshop_id': 2,
                    'workshop_name': '鐑涧杞﹂棿',
                    'machines': [],
                    'workshop_total': {'input': 100.0, 'output': 97.0, 'scrap': 3.0, 'yield_rate': 97.0},
                }
            ],
            'factory_total': {'input': 100.0, 'output': 97.0, 'scrap': 3.0, 'yield_rate': 97.0},
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.build_live_aggregation', fake_build_live_aggregation)

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.get(
        '/api/v1/aggregation/live',
        params={'business_date': '2026-03-27', 'workshop_id': 2},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json()['overall_progress']['submitted_cells'] == 4
    assert response.json()['workshops'][0]['workshop_name'] == '鐑涧杞﹂棿'

    app.dependency_overrides.clear()


def test_live_aggregation_detail_endpoint_calls_service(monkeypatch) -> None:
    current_user = User(
        id=7,
        username='chief-stat',
        password_hash='x',
        name='Chief Stat',
        role='statistician',
        data_scope_type='all',
        is_active=True,
    )

    def fake_get_db():
        yield DummyDB(current_user)

    def fake_detail(db, *, business_date, workshop_id, machine_id, shift_id, current_user):
        assert business_date == date(2026, 3, 27)
        assert workshop_id == 2
        assert machine_id == 11
        assert shift_id == 3
        return {
            'business_date': '2026-03-27',
            'workshop_id': 2,
            'machine_id': 11,
            'shift_id': 3,
            'items': [
                {
                    'tracking_card_no': 'RA240001',
                    'entry_id': 9,
                    'entry_status': 'submitted',
                    'entry_type': 'completed',
                    'input_weight': 10.0,
                    'output_weight': 9.7,
                    'scrap_weight': 0.3,
                    'yield_rate': 97.0,
                }
            ],
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.build_live_cell_detail', fake_detail)

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.get(
        '/api/v1/aggregation/live/detail',
        params={
            'business_date': '2026-03-27',
            'workshop_id': 2,
            'machine_id': 11,
            'shift_id': 3,
        },
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json()['items'][0]['tracking_card_no'] == 'RA240001'

    app.dependency_overrides.clear()


def test_live_aggregation_rejects_query_token_auth(monkeypatch) -> None:
    current_user = User(
        id=7,
        username='chief-stat',
        password_hash='x',
        name='Chief Stat',
        role='statistician',
        data_scope_type='all',
        is_active=True,
    )

    def fake_get_db():
        yield DummyDB(current_user)

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(
        'app.routers.realtime.realtime_service.build_live_aggregation',
        lambda *args, **kwargs: {
            'business_date': '2026-03-27',
            'overall_progress': {'submitted_cells': 0, 'total_cells': 0},
            'workshops': [],
            'factory_total': {'input': 0.0, 'output': 0.0, 'scrap': 0.0, 'yield_rate': 0.0},
        },
    )

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.get(
        '/api/v1/aggregation/live',
        params={'business_date': '2026-03-27', 'token': token},
    )

    assert response.status_code == 401

    app.dependency_overrides.clear()
