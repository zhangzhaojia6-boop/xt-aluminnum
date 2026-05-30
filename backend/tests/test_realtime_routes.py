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
    assert app.url_path_for('live-active-business-date') == '/api/v1/aggregation/live/active-date'
    assert app.url_path_for('live-aggregation-detail') == '/api/v1/aggregation/live/detail'
    assert app.url_path_for('live-fill-details') == '/api/v1/aggregation/live/fill-details'
    assert app.url_path_for('live-pending-assignment') == '/api/v1/aggregation/live/pending-assignment'
    assert app.url_path_for('live-missing-output-resolve', entry_id=7) == '/api/v1/aggregation/live/missing-output/7'


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
            'owner_daily_status': {
                'submitted_count': 1,
                'total_count': 1,
                'totals': [{'key': 'total_electricity_kwh', 'label': '全厂用电', 'value': 1200.0, 'unit': 'kWh'}],
                'items': [],
            },
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
    assert response.json()['owner_daily_status']['totals'][0]['key'] == 'total_electricity_kwh'

    app.dependency_overrides.clear()


def test_live_active_business_date_endpoint_calls_service(monkeypatch) -> None:
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

    def fake_resolve_live_business_date(db, *, workshop_id=None):
        assert workshop_id is None
        return {'business_date': '2026-05-06', 'source': 'recent_upload', 'recent_entry_count': 7}

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.resolve_live_business_date', fake_resolve_live_business_date)

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.get(
        '/api/v1/aggregation/live/active-date',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json() == {'business_date': '2026-05-06', 'source': 'recent_upload', 'recent_entry_count': 7}

    app.dependency_overrides.clear()


def test_live_active_business_date_passes_workshop_scope_for_shift_leader(monkeypatch) -> None:
    current_user = User(
        id=42,
        username='lz2050-leader',
        password_hash='x',
        name='Cold Roll Leader',
        role='shift_leader',
        workshop_id=5,
        data_scope_type='self_workshop',
        is_active=True,
    )

    def fake_get_db():
        yield DummyDB(current_user)

    captured = {}

    def fake_resolve_live_business_date(db, *, workshop_id=None):
        captured['workshop_id'] = workshop_id
        return {'business_date': '2026-05-06', 'source': 'recent_upload', 'recent_entry_count': 3}

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.resolve_live_business_date', fake_resolve_live_business_date)

    token = create_access_token(subject=str(current_user.id))
    response = TestClient(app).get(
        '/api/v1/aggregation/live/active-date',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert captured['workshop_id'] == 5

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


def test_live_fill_details_endpoint_calls_service(monkeypatch) -> None:
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

    def fake_detail(db, *, business_date, workshop_id, search, limit, current_user):
        assert business_date == date(2026, 5, 6)
        assert workshop_id == 2
        assert search == '1#'
        assert limit == 20
        assert current_user.id == 7
        return {
            'business_date': '2026-05-06',
            'workshop_id': 2,
            'total': 1,
            'summary': {
                'entry_count': 1,
                'machine_count': 1,
                'owner_count': 1,
                'output': 96.0,
                'energy_kwh': 120.0,
                'gas_m3': 0.0,
                'source_counts': {'work_order_entry': 1},
            },
            'items': [
                {
                    'row_id': 'entry-101',
                    'source_type': 'work_order_entry',
                    'source_label': '扫码卷明细',
                    'entry_id': 101,
                    'tracking_card_no': 'RA260506001',
                    'business_date': '2026-05-06',
                    'workshop_id': 2,
                    'workshop_name': '2050冷轧车间',
                    'machine_id': 11,
                    'machine_name': '1#机列',
                    'shift_id': 3,
                    'shift_name': '夜班',
                    'responsible_user_id': 9,
                    'responsible_name': '张三',
                    'responsible_username': 'operator-1',
                    'status': 'submitted',
                    'entry_type': 'mobile_coil',
                    'output_weight': 96.0,
                    'energy_kwh': 120.0,
                    'search_text': '1#机列 张三 RA260506001',
                }
            ],
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.build_fill_detail_ledger', fake_detail)

    token = create_access_token(subject=str(current_user.id))
    response = TestClient(app).get(
        '/api/v1/aggregation/live/fill-details',
        params={'business_date': '2026-05-06', 'workshop_id': 2, 'search': '1#', 'limit': 20},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json()['items'][0]['responsible_name'] == '张三'
    assert response.json()['summary']['machine_count'] == 1

    app.dependency_overrides.clear()


def test_live_pending_assignment_endpoint_calls_service(monkeypatch) -> None:
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

    def fake_detail(db, *, business_date, workshop_id, current_user):
        assert business_date == date(2026, 5, 6)
        assert workshop_id == 2
        assert current_user.id == 7
        return {
            'business_date': '2026-05-06',
            'workshop_id': 2,
            'total': 1,
            'summary': {
                'entry_count': 1,
                'draft_entry_count': 1,
                'formal_entry_count': 0,
                'missing_machine_count': 1,
                'missing_shift_count': 0,
                'input': 100.0,
                'output': 96.0,
                'scrap': 4.0,
            },
            'items': [
                {
                    'tracking_card_no': 'RA260506001',
                    'entry_id': 101,
                    'work_order_id': 101,
                    'business_date': '2026-05-06',
                    'workshop_id': 2,
                    'workshop_name': '2050冷轧车间',
                    'shift_id': 3,
                    'shift_name': '夜班',
                    'machine_id': None,
                    'entry_status': 'draft',
                    'entry_type': 'mobile_coil',
                    'input_weight': 100.0,
                    'output_weight': 96.0,
                    'scrap_weight': 4.0,
                    'missing_fields': ['machine_id'],
                    'created_by_user_id': 9,
                    'created_at': '2026-05-06T09:30:00',
                }
            ],
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.build_pending_assignment_detail', fake_detail)

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.get(
        '/api/v1/aggregation/live/pending-assignment',
        params={'business_date': '2026-05-06', 'workshop_id': 2},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json()['summary']['output'] == 96.0
    assert response.json()['items'][0]['missing_fields'] == ['machine_id']

    app.dependency_overrides.clear()


def test_live_pending_assignment_endpoint_passes_workshop_scope(monkeypatch) -> None:
    current_user = User(
        id=8,
        username='workshop-reviewer',
        password_hash='x',
        name='Workshop Reviewer',
        role='workshop_director',
        workshop_id=2,
        data_scope_type='self_workshop',
        is_active=True,
    )

    def fake_get_db():
        yield DummyDB(current_user)

    def fake_detail(db, *, business_date, workshop_id, current_user):
        assert business_date == date(2026, 5, 6)
        assert workshop_id is None
        assert current_user.workshop_id == 2
        return {
            'business_date': '2026-05-06',
            'workshop_id': 2,
            'total': 0,
            'summary': {
                'entry_count': 0,
                'draft_entry_count': 0,
                'formal_entry_count': 0,
                'missing_machine_count': 0,
                'missing_shift_count': 0,
                'input': 0.0,
                'output': 0.0,
                'scrap': 0.0,
            },
            'items': [],
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.build_pending_assignment_detail', fake_detail)

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.get(
        '/api/v1/aggregation/live/pending-assignment',
        params={'business_date': '2026-05-06'},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json()['workshop_id'] == 2

    app.dependency_overrides.clear()


def test_live_missing_output_resolve_endpoint_calls_service(monkeypatch) -> None:
    current_user = User(
        id=7,
        username='chief-stat',
        password_hash='x',
        name='Chief Stat',
        role='statistician',
        data_scope_type='all',
        is_active=True,
    )
    calls = {}

    def fake_get_db():
        yield DummyDB(current_user)

    def fake_resolve(db, *, entry_id, output_weight, reason, current_user, ip_address=None, user_agent=None):
        calls['entry_id'] = entry_id
        calls['output_weight'] = output_weight
        calls['reason'] = reason
        calls['user_id'] = current_user.id
        calls['ip_address'] = ip_address
        calls['user_agent'] = user_agent
        return {
            'entry_id': entry_id,
            'work_order_id': 603,
            'output_weight': output_weight,
            'yield_rate': 96.0,
            'entry_status': 'submitted',
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr('app.routers.realtime.realtime_service.resolve_missing_output_weight', fake_resolve)

    token = create_access_token(subject=str(current_user.id))
    client = TestClient(app)
    response = client.patch(
        '/api/v1/aggregation/live/missing-output/603',
        json={'output_weight': 96.0, 'reason': '现场复核产出重量'},
        headers={'Authorization': f'Bearer {token}', 'User-Agent': 'route-test'},
    )

    assert response.status_code == 200
    assert response.json() == {
        'entry_id': 603,
        'work_order_id': 603,
        'output_weight': 96.0,
        'yield_rate': 96.0,
        'entry_status': 'submitted',
    }
    assert calls['entry_id'] == 603
    assert calls['output_weight'] == 96.0
    assert calls['reason'] == '现场复核产出重量'
    assert calls['user_id'] == 7
    assert calls['user_agent'] == 'route-test'

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
