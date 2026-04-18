from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.core.permissions import get_current_manager_user
from app.core.deps import get_current_user
from app.main import app
from app.schemas.dashboard import WorkshopDashboardResponse


class DummyDB:
    pass


def test_factory_dashboard_exposes_leader_summary_payload(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user():
        return SimpleNamespace(
            id=7,
            role='manager',
            is_admin=False,
            is_manager=True,
            is_reviewer=False,
            workshop_id=None,
            data_scope_type='all',
        )

    def fake_dashboard(_db, *, target_date):
        assert target_date == date(2026, 4, 10)
        return {
            'target_date': '2026-04-10',
            'leader_summary': {
                'summary_text': '2026-04-10，今日产量 123.40 吨，异常 0 条。',
                'summary_source': 'deterministic',
            },
            'leader_metrics': {
                'today_total_output': 123.4,
                'energy_per_ton': 3.21,
                'contract_weight': 98.7,
                'yield_rate': 96.5,
                'shipment_weight': 55.0,
                'storage_inbound_area': 1200.0,
            },
            'history_digest': {
                'daily_snapshots': [
                    {'date': '2026-04-09', 'output_weight': 118.0},
                    {'date': '2026-04-10', 'output_weight': 123.4},
                ],
                'month_archive': {'total_output': 1234.5},
                'year_archive': {'total_output': 5678.9},
            },
            'delivery_ready': True,
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_manager_user] = fake_get_user
    monkeypatch.setattr('app.routers.dashboard.report_service.build_factory_dashboard', fake_dashboard)

    client = TestClient(app)
    response = client.get('/api/v1/dashboard/factory-director', params={'target_date': '2026-04-10'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['target_date'] == '2026-04-10'
    assert payload['leader_summary']['summary_text'] == '2026-04-10，今日产量 123.40 吨，异常 0 条。'
    assert payload['leader_summary']['summary_source'] == 'deterministic'
    assert payload['leader_metrics']['today_total_output'] == 123.4
    assert payload['leader_metrics']['yield_rate'] == 96.5
    assert payload['leader_metrics']['shipment_weight'] == 55.0
    assert payload['leader_metrics']['storage_inbound_area'] == 1200.0
    assert payload['history_digest']['daily_snapshots'][1]['output_weight'] == 123.4
    assert payload['history_digest']['month_archive']['total_output'] == 1234.5
    assert payload['delivery_ready'] is True

    app.dependency_overrides.clear()


def test_workshop_dashboard_exposes_owner_lane_payload(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user():
        return SimpleNamespace(
            id=8,
            role='manager',
            is_admin=False,
            is_manager=True,
            is_reviewer=False,
            workshop_id=14,
            data_scope_type='all',
        )

    def fake_dashboard(_db, *, target_date, workshop_id):
        assert target_date == date(2026, 4, 10)
        assert workshop_id == 14
        return {
            'target_date': '2026-04-10',
            'workshop_id': 14,
            'total_output': 88.0,
            'month_to_date_output': 1000.0,
            'pending_shift_count': 1,
            'mobile_reporting_summary': {'reporting_rate': 100.0},
            'energy_summary': {'energy_per_ton': 2.5},
            'energy_lane': [{'source': 'owner_only', 'water_value': 50.0}],
            'inventory_lane': [{'shipment_weight': 55.0, 'storage_inbound_area': 1200.0, 'actual_inventory_weight': 980.0}],
            'exception_lane': {'returned_shift_count': 0},
            'reminder_summary': {'today_reminder_count': 0},
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.dashboard.report_service.build_workshop_dashboard', fake_dashboard)

    client = TestClient(app)
    response = client.get('/api/v1/dashboard/workshop-director', params={'target_date': '2026-04-10', 'workshop_id': 14})

    assert response.status_code == 200
    payload = response.json()
    assert payload['workshop_id'] == 14
    assert payload['inventory_lane'][0]['shipment_weight'] == 55.0
    assert payload['inventory_lane'][0]['storage_inbound_area'] == 1200.0
    assert payload['inventory_lane'][0]['actual_inventory_weight'] == 980.0
    assert payload['energy_lane'][0]['source'] == 'owner_only'
    assert payload['energy_lane'][0]['water_value'] == 50.0

    app.dependency_overrides.clear()


def test_workshop_dashboard_response_model_accepts_owner_lane_fields() -> None:
    payload = WorkshopDashboardResponse(
        target_date='2026-04-10',
        workshop_id=14,
        total_output=88.0,
        month_to_date_output=1000.0,
        mobile_reporting_summary={'reporting_rate': 100.0},
        energy_summary={'energy_per_ton': 2.5},
        energy_lane=[{'source': 'owner_only', 'water_value': 50.0}],
        inventory_lane=[{'shipment_weight': 55.0, 'storage_inbound_area': 1200.0, 'actual_inventory_weight': 980.0}],
        exception_lane={'returned_shift_count': 0},
        reminder_summary={'today_reminder_count': 0},
    )

    assert payload.workshop_id == 14
    assert payload.inventory_lane[0]['shipment_weight'] == 55.0
    assert payload.energy_lane[0]['source'] == 'owner_only'
