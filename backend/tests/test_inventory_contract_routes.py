from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app


class DummyDB:
    pass


def _fake_db():
    yield DummyDB()


def _fake_user():
    return SimpleNamespace(
        id=1,
        username='admin',
        role='admin',
        is_admin=True,
        is_manager=True,
        is_reviewer=True,
        workshop_id=None,
        data_scope_type='all',
    )


def test_inventory_and_contract_routes_are_registered() -> None:
    assert app.url_path_for('inventory-summary') == '/api/v1/inventory/summary'
    assert app.url_path_for('inventory-export') == '/api/v1/inventory/export'
    assert app.url_path_for('contracts-summary') == '/api/v1/contracts/summary'
    assert app.url_path_for('contracts-export') == '/api/v1/contracts/export'


def test_inventory_summary_matches_frontend_contract(monkeypatch) -> None:
    def fake_inventory(db, *, target_date, workshop_id=None):
        assert isinstance(db, DummyDB)
        assert target_date == date(2026, 6, 2)
        assert workshop_id == 3
        return [
            {
                'workshop_id': 3,
                'workshop_name': '成品库',
                'team_name': '内勤',
                'source_label': '专项补录',
                'storage_finished': 12.5,
                'shipment_weight': 4.25,
                'actual_inventory_weight': 88.0,
            }
        ]

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user
    monkeypatch.setattr('app.routers.inventory.summarize_mobile_inventory', fake_inventory)

    client = TestClient(app)
    response = client.get(
        '/api/v1/inventory/summary',
        params={'date_from': '2026-06-02', 'date_to': '2026-06-02', 'warehouse_id': 3},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['kpi']['current_stock'] == 88.0
    assert data['kpi']['inbound_today'] == 12.5
    assert data['kpi']['outbound_today'] == 4.25
    assert data['trend']['labels'] == ['2026-06-02']
    assert data['transactions'][0]['direction'] == 'inbound'
    assert data['warehouses'][0]['name'] == '成品库'

    export_response = client.get('/api/v1/inventory/export', params={'date_from': '2026-06-02', 'warehouse_id': 3})
    assert export_response.status_code == 200
    assert export_response.headers['content-type'].startswith('text/csv')
    assert '成品库' in export_response.text

    app.dependency_overrides.clear()


def test_contract_summary_matches_frontend_contract(monkeypatch) -> None:
    def fake_projection(db, *, target_date):
        assert isinstance(db, DummyDB)
        assert target_date == date(2026, 6, 2)
        return {'month_to_date_contract_weight': 120.0}

    def fake_progress(db, *, target_date):
        assert isinstance(db, DummyDB)
        assert target_date == date(2026, 6, 2)
        return {
            'active_contract_count': 1,
            'stalled_contract_count': 1,
            'contracts': [
                {
                    'contract_no': 'HT-001',
                    'status': 'stalled',
                    'today_advanced_weight': 20.0,
                    'remaining_weight': 80.0,
                },
                {
                    'contract_no': 'HT-002',
                    'status': 'active',
                    'today_advanced_weight': 5.0,
                    'remaining_weight': 45.0,
                },
            ],
        }

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user
    monkeypatch.setattr('app.routers.contracts.build_contract_projection', fake_projection)
    monkeypatch.setattr('app.routers.contracts.build_contract_progress_projection', fake_progress)

    client = TestClient(app)
    response = client.get('/api/v1/contracts/summary', params={'date_to': '2026-06-02', 'status': 'overdue'})

    assert response.status_code == 200
    data = response.json()
    assert data['kpi']['active_count'] == 1
    assert data['kpi']['overdue_count'] == 1
    assert data['kpi']['mtd_delivery_tons'] == 120.0
    assert data['contracts'][0]['contract_no'] == 'HT-001'
    assert data['contracts'][0]['status'] == 'overdue'
    assert data['progress']['labels'] == ['HT-001']

    export_response = client.get('/api/v1/contracts/export', params={'date_to': '2026-06-02'})
    assert export_response.status_code == 200
    assert export_response.headers['content-type'].startswith('text/csv')
    assert 'HT-001' in export_response.text

    app.dependency_overrides.clear()
