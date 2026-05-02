from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_work_order_routes_are_registered() -> None:
    assert app.url_path_for('template-detail', workshop_type='casting') == '/api/v1/templates/casting'
    assert app.url_path_for('work-orders-create') == '/api/v1/work-orders/'
    assert app.url_path_for('work-order-update', work_order_id='1') == '/api/v1/work-orders/1'
    assert app.url_path_for('work-order-detail', tracking_card_no='RA240001') == '/api/v1/work-orders/RA240001'
    assert app.url_path_for('work-order-entry-create', work_order_id='1') == '/api/v1/work-orders/1/entries'
    assert app.url_path_for('work-order-entry-submit', entry_id='9') == '/api/v1/work-orders/entries/9/submit'
    assert app.url_path_for('field-amendment-create') == '/api/v1/amendments/'
    assert app.url_path_for('field-amendment-approve', amendment_id='5') == '/api/v1/amendments/5/approve'


def test_submit_endpoint_calls_work_order_service(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='leader',
            password_hash='x',
            name='Leader',
            role='shift_leader',
            workshop_id=1,
            is_active=True,
        )

    def fake_submit(db, *, entry_id, operator, override_reason=None, ip_address=None, user_agent=None):
        assert entry_id == 9
        assert operator.id == 1
        assert override_reason is None
        assert ip_address == 'testclient'
        assert user_agent
        calls.append((entry_id, operator.role))
        now = datetime(2026, 3, 27, 8, 0, 0)
        return {
            'id': 9,
            'work_order_id': 1,
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': date(2026, 3, 27),
            'input_weight': 9500,
            'output_weight': 9220,
            'verified_input_weight': None,
            'verified_output_weight': None,
            'yield_rate': 97.05,
            'entry_type': 'completed',
            'entry_status': 'submitted',
            'locked_fields': ['input_weight', 'output_weight'],
            'submitted_at': now,
            'verified_at': None,
            'approved_at': None,
            'created_by': 1,
            'created_at': now,
            'updated_at': now,
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.work_orders.work_order_service.submit_entry', fake_submit)

    client = TestClient(app)
    response = client.post('/api/v1/work-orders/entries/9/submit')

    assert response.status_code == 200
    assert response.json()['entry_status'] == 'submitted'
    assert calls == [(9, 'shift_leader')]

    app.dependency_overrides.clear()


def test_update_work_order_endpoint_calls_service(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=3,
            username='contracts',
            password_hash='x',
            name='Contracts',
            role='contracts',
            is_active=True,
        )

    def fake_update(db, *, work_order_id, payload, operator, ip_address=None, user_agent=None):
        assert work_order_id == 1
        assert payload == {'contract_no': 'HT-2026-001', 'customer_name': 'ACME'}
        assert operator.id == 3
        assert ip_address == 'testclient'
        assert user_agent
        calls.append(work_order_id)
        now = datetime(2026, 3, 27, 8, 30, 0)
        return {
            'id': 1,
            'tracking_card_no': 'RA240001',
            'process_route_code': 'RA',
            'alloy_grade': 'A1050',
            'contract_no': 'HT-2026-001',
            'customer_name': 'ACME',
            'contract_weight': 9220,
            'current_station': '热轧',
            'previous_stage_output': None,
            'overall_status': 'in_progress',
            'created_by': 1,
            'created_at': now,
            'updated_at': now,
            'entries': [],
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.work_orders.work_order_service.update_work_order', fake_update)

    client = TestClient(app)
    response = client.patch('/api/v1/work-orders/1', json={'contract_no': 'HT-2026-001', 'customer_name': 'ACME'})

    assert response.status_code == 200
    assert response.json()['contract_no'] == 'HT-2026-001'
    assert calls == [1]

    app.dependency_overrides.clear()


def test_create_entry_endpoint_accepts_ocr_submission_id(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='leader',
            password_hash='x',
            name='Leader',
            role='shift_leader',
            workshop_id=1,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_add_entry(db, *, work_order_id, payload, operator, idempotency_key=None, ip_address=None, user_agent=None):
        assert work_order_id == 1
        assert payload['ocr_submission_id'] == 12
        assert payload['input_weight'] == 9500
        assert operator.id == 1
        assert idempotency_key is None
        assert ip_address == 'testclient'
        assert user_agent
        calls.append(payload['ocr_submission_id'])
        now = datetime(2026, 3, 27, 10, 0, 0)
        return {
            'id': 15,
            'work_order_id': 1,
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': date(2026, 3, 27),
            'input_weight': 9500,
            'output_weight': 9220,
            'verified_input_weight': None,
            'verified_output_weight': None,
            'yield_rate': 97.05,
            'entry_type': 'completed',
            'entry_status': 'draft',
            'locked_fields': [],
            'submitted_at': None,
            'verified_at': None,
            'approved_at': None,
            'created_by': 1,
            'created_at': now,
            'updated_at': now,
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.work_orders.work_order_service.add_entry', fake_add_entry)

    client = TestClient(app)
    response = client.post(
        '/api/v1/work-orders/1/entries',
        json={
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': '2026-03-27',
            'input_weight': 9500,
            'output_weight': 9220,
            'entry_type': 'completed',
            'ocr_submission_id': 12,
        },
    )

    assert response.status_code == 200
    assert response.json()['id'] == 15
    assert calls == [12]

    app.dependency_overrides.clear()


def test_create_entry_endpoint_forwards_flow_payload(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='leader',
            password_hash='x',
            name='Leader',
            role='shift_leader',
            workshop_id=1,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_add_entry(db, *, work_order_id, payload, operator, idempotency_key=None, ip_address=None, user_agent=None):
        assert payload['extra_payload']['flow']['current_process'] == '轧制'
        assert payload['extra_payload']['flow']['flow_source'] == 'mes_projection'
        calls.append(payload['extra_payload']['flow'])
        now = datetime(2026, 5, 2, 10, 0, 0)
        return {
            'id': 17,
            'work_order_id': work_order_id,
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': date(2026, 5, 2),
            'input_weight': 1000,
            'output_weight': 960,
            'verified_input_weight': None,
            'verified_output_weight': None,
            'yield_rate': 96.0,
            'entry_type': 'completed',
            'entry_status': 'draft',
            'extra_payload': {'flow': payload['extra_payload']['flow']},
            'qc_payload': {},
            'locked_fields': [],
            'submitted_at': None,
            'verified_at': None,
            'approved_at': None,
            'created_by': 1,
            'created_at': now,
            'updated_at': now,
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.work_orders.work_order_service.add_entry', fake_add_entry)

    client = TestClient(app)
    response = client.post(
        '/api/v1/work-orders/1/entries',
        json={
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': '2026-05-02',
            'input_weight': 1000,
            'output_weight': 960,
            'entry_type': 'completed',
            'extra_payload': {
                'flow': {
                    'current_workshop': '冷轧',
                    'current_process': '轧制',
                    'next_workshop': '精整',
                    'next_process': '剪切',
                    'flow_source': 'mes_projection',
                }
            },
        },
    )

    assert response.status_code == 200
    assert response.json()['extra_payload']['flow']['next_process'] == '剪切'
    assert len(calls) == 1

    app.dependency_overrides.clear()


def test_create_entry_endpoint_forwards_idempotency_key(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='leader',
            password_hash='x',
            name='Leader',
            role='shift_leader',
            workshop_id=1,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_add_entry(
        db,
        *,
        work_order_id,
        payload,
        operator,
        idempotency_key=None,
        ip_address=None,
        user_agent=None,
    ):
        assert work_order_id == 1
        assert operator.id == 1
        assert idempotency_key == '550e8400-e29b-41d4-a716-446655440000'
        assert ip_address == 'testclient'
        assert user_agent
        calls.append(idempotency_key)
        now = datetime(2026, 3, 27, 10, 5, 0)
        return {
            'id': 16,
            'work_order_id': 1,
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': date(2026, 3, 27),
            'input_weight': 9500,
            'output_weight': 9220,
            'verified_input_weight': None,
            'verified_output_weight': None,
            'yield_rate': 97.05,
            'entry_type': 'completed',
            'entry_status': 'draft',
            'locked_fields': [],
            'submitted_at': None,
            'verified_at': None,
            'approved_at': None,
            'created_by': 1,
            'created_at': now,
            'updated_at': now,
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.work_orders.work_order_service.add_entry', fake_add_entry)

    client = TestClient(app)
    response = client.post(
        '/api/v1/work-orders/1/entries',
        headers={'X-Idempotency-Key': '550e8400-e29b-41d4-a716-446655440000'},
        json={
            'workshop_id': 1,
            'machine_id': 2,
            'shift_id': 3,
            'business_date': '2026-03-27',
            'input_weight': 9500,
            'output_weight': 9220,
            'entry_type': 'completed',
        },
    )

    assert response.status_code == 200
    assert response.json()['id'] == 16
    assert calls == ['550e8400-e29b-41d4-a716-446655440000']

    app.dependency_overrides.clear()


def test_approve_amendment_endpoint_calls_service(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=2,
            username='admin',
            password_hash='x',
            name='Admin',
            role='admin',
            is_active=True,
        )

    def fake_approve(db, *, amendment_id, operator):
        assert amendment_id == 5
        assert operator.id == 2
        calls.append(amendment_id)
        now = datetime(2026, 3, 27, 9, 0, 0)
        return {
            'id': 5,
            'table_name': 'work_order_entries',
            'record_id': 9,
            'field_name': 'input_weight',
            'old_value': '9500',
            'new_value': '9520',
            'reason': 'weighbridge correction',
            'requested_by': 1,
            'requested_at': now,
            'approved_by': 2,
            'approved_at': now,
            'status': 'approved',
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.work_orders.work_order_service.approve_amendment', fake_approve)

    client = TestClient(app)
    response = client.patch('/api/v1/amendments/5/approve')

    assert response.status_code == 200
    assert response.json()['status'] == 'approved'
    assert calls == [5]

    app.dependency_overrides.clear()
