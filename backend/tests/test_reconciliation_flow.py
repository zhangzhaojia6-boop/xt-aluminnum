from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def _reconciliation_item_response(*, status: str, note: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=11,
        business_date=date(2026, 3, 25),
        reconciliation_type='production_vs_mes',
        source_a='shift_production_data',
        source_b='mes_export',
        dimension_key='total',
        field_name='output_weight',
        source_a_value='100',
        source_b_value='95',
        diff_value=5.0,
        status=status,
        resolved_by=2,
        resolved_at=datetime(2026, 3, 25, 9, 0, 0),
        resolve_note=note,
        created_at=datetime(2026, 3, 25, 8, 0, 0),
        updated_at=datetime(2026, 3, 25, 9, 0, 0),
    )


def test_reconciliation_generate_and_confirm(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=2, username='stat', password_hash='x', name='Stat', role='stat', is_active=True)

    def fake_generate(db, *, business_date, reconciliation_type, operator):
        assert business_date == date(2026, 3, 25)
        assert reconciliation_type == 'production_vs_mes'
        assert operator.id == 2
        return [
            SimpleNamespace(
                id=11,
                business_date=business_date,
                reconciliation_type='production_vs_mes',
                source_a='shift_production_data',
                source_b='mes_export',
                dimension_key='total',
                field_name='output_weight',
                source_a_value='100',
                source_b_value='95',
                diff_value=5.0,
                status='open',
                resolved_by=None,
                resolved_at=None,
                resolve_note=None,
                created_at=datetime(2026, 3, 25, 8, 0, 0),
                updated_at=datetime(2026, 3, 25, 8, 0, 0),
            )
        ]

    def fake_update(db, *, item_id, action, operator, note=None):
        assert item_id == 11
        assert action == 'confirm'
        assert operator.id == 2
        return SimpleNamespace(
            id=11,
            business_date=date(2026, 3, 25),
            reconciliation_type='production_vs_mes',
            source_a='shift_production_data',
            source_b='mes_export',
            dimension_key='total',
            field_name='output_weight',
            source_a_value='100',
            source_b_value='95',
            diff_value=5.0,
            status='confirmed',
            resolved_by=2,
            resolved_at=datetime(2026, 3, 25, 9, 0, 0),
            resolve_note=note,
            created_at=datetime(2026, 3, 25, 8, 0, 0),
            updated_at=datetime(2026, 3, 25, 9, 0, 0),
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reconciliation.reconciliation_service.generate_reconciliation', fake_generate)
    monkeypatch.setattr('app.routers.reconciliation.reconciliation_service.update_item_status', fake_update)

    client = TestClient(app)
    response = client.post(
        '/api/v1/reconciliation/generate',
        json={'business_date': '2026-03-25', 'reconciliation_type': 'production_vs_mes'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body[0]['id'] == 11

    confirm = client.post('/api/v1/reconciliation/items/11/confirm', json={'note': 'ok'})
    assert confirm.status_code == 200
    assert confirm.json()['status'] == 'confirmed'

    app.dependency_overrides.clear()


def test_reconciliation_actions_reject_blank_note(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=2, username='stat', password_hash='x', name='Stat', role='stat', is_active=True)

    calls: list[str | None] = []

    def fake_update(db, *, item_id, action, operator, note=None):
        calls.append(note)
        return _reconciliation_item_response(status='confirmed', note=note)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reconciliation.reconciliation_service.update_item_status', fake_update)

    try:
        client = TestClient(app)
        for action in ('confirm', 'ignore', 'correct'):
            for payload in ({}, {'note': None}, {'note': '   '}):
                response = client.post(f'/api/v1/reconciliation/items/11/{action}', json=payload)
                assert response.status_code == 422
        assert calls == []
    finally:
        app.dependency_overrides.clear()


def test_reconciliation_actions_trim_note_before_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=2, username='stat', password_hash='x', name='Stat', role='stat', is_active=True)

    calls: list[tuple[str, str | None]] = []
    status_by_action = {
        'confirm': 'confirmed',
        'ignore': 'ignored',
        'correct': 'corrected',
    }

    def fake_update(db, *, item_id, action, operator, note=None):
        calls.append((action, note))
        return _reconciliation_item_response(status=status_by_action[action], note=note)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reconciliation.reconciliation_service.update_item_status', fake_update)

    try:
        client = TestClient(app)
        cases = [
            ('confirm', ' 已核对业务口径 ', '已核对业务口径'),
            ('ignore', ' 本期不纳入处理 ', '本期不纳入处理'),
            ('correct', ' 已按现场数据修正 ', '已按现场数据修正'),
        ]

        for action, raw_note, expected_note in cases:
            response = client.post(f'/api/v1/reconciliation/items/11/{action}', json={'note': raw_note})
            assert response.status_code == 200
            assert response.json()['resolve_note'] == expected_note

        assert calls == [
            ('confirm', '已核对业务口径'),
            ('ignore', '本期不纳入处理'),
            ('correct', '已按现场数据修正'),
        ]
    finally:
        app.dependency_overrides.clear()
