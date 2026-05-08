from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User
from app.routers import imports as imports_router
from app.services.daily_production_mapping_service import (
    DailyProductionMappingPreview,
    DailyProductionMappingRow,
    MappingCandidate,
)


def test_daily_production_mapping_preview_route_returns_serialized_preview(monkeypatch) -> None:
    fake_db = object()
    captured: dict[str, object] = {}

    def fake_get_db():
        yield fake_db

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_build_preview(db, *, batch_id=None) -> DailyProductionMappingPreview:
        captured['db'] = db
        captured['batch_id'] = batch_id
        return DailyProductionMappingPreview(
            batch_id=7,
            batch_no='IMP-DAILY-7',
            business_date='2026-05-03',
            source_unit='t',
            total_rows=2,
            ready_rows=1,
            needs_equipment_mapping_rows=0,
            unresolved_rows=1,
            rows=[
                DailyProductionMappingRow(
                    row_index=3,
                    business_date='2026-05-03',
                    source_unit='t',
                    workshop_label='铸锭',
                    project_label=None,
                    daily_input_tons=314.19,
                    month_to_date_input_tons=None,
                    daily_output_tons=301.1,
                    month_to_date_output_tons=None,
                    daily_scrap_tons=13.09,
                    month_to_date_scrap_tons=None,
                    status='ready',
                    expected_workshop_code='ZD',
                    expected_equipment_code=None,
                    workshop_id=11,
                    workshop_code='ZD',
                    workshop_name='铸锭',
                    equipment_id=None,
                    equipment_code=None,
                    equipment_name=None,
                    candidate_workshops=[],
                    candidate_equipment=[],
                    issues=[],
                ),
                DailyProductionMappingRow(
                    row_index=7,
                    business_date='2026-05-03',
                    source_unit='t',
                    workshop_label='冷轧',
                    project_label='1650',
                    daily_input_tons=88.0,
                    month_to_date_input_tons=None,
                    daily_output_tons=79.0,
                    month_to_date_output_tons=None,
                    daily_scrap_tons=9.0,
                    month_to_date_scrap_tons=None,
                    status='unresolved_workshop',
                    expected_workshop_code=None,
                    expected_equipment_code=None,
                    workshop_id=None,
                    workshop_code=None,
                    workshop_name=None,
                    equipment_id=None,
                    equipment_code=None,
                    equipment_name=None,
                    candidate_workshops=[
                        MappingCandidate(id=31, code='JZ', name='精整车间'),
                    ],
                    candidate_equipment=[
                        MappingCandidate(id=301, code='JZ-ZJ1', name='纵剪1#'),
                    ],
                    issues=[{'code': 'unresolved_workshop', 'message': '每日产量行未匹配到高置信车间主数据。'}],
                    candidate_workshops=[
                        MappingCandidate(
                            entity_type='workshop',
                            id=7,
                            code='LZ3',
                            name='冷轧三车间',
                            workshop_id=7,
                            workshop_code='LZ3',
                            equipment_type=None,
                            match_reason='workshop_label_match',
                        )
                    ],
                    candidate_equipment=[],
                ),
            ],
        )

    monkeypatch.setattr(imports_router, 'build_daily_production_mapping_preview', fake_build_preview)

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    try:
        client = TestClient(app)
        response = client.get('/api/v1/imports/daily-production/mapping-preview?batch_id=7')

        assert response.status_code == 200
        payload = response.json()
        assert captured == {'db': fake_db, 'batch_id': 7}
        assert payload['batch_id'] == 7
        assert payload['batch_no'] == 'IMP-DAILY-7'
        assert payload['source_unit'] == 't'
        assert payload['total_rows'] == 2
        assert payload['ready_rows'] == 1
        assert payload['unresolved_rows'] == 1
        assert payload['rows'][0]['status'] == 'ready'
        assert payload['rows'][0]['daily_output_tons'] == 301.1
        assert payload['rows'][1]['status'] == 'unresolved_workshop'
        assert payload['rows'][1]['candidate_workshops'][0]['code'] == 'JZ'
        assert payload['rows'][1]['candidate_equipment'][0]['code'] == 'JZ-ZJ1'
        assert payload['rows'][1]['issues'][0]['code'] == 'unresolved_workshop'
        assert payload['rows'][1]['candidate_workshops'][0]['code'] == 'LZ3'
        assert payload['rows'][1]['candidate_equipment'] == []
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
