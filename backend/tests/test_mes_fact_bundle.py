from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.core.permissions import get_current_manager_user
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop
from app.models.mes import (
    MesCoilSnapshot,
    MesMaterialRecord,
    MesStockRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
)
from app.schemas.reports import TemplateDailyReportPreviewResponse
from app.services.report import mes_fact_bundle, template_daily_report


BUSINESS_DATE = date(2026, 6, 18)


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-fact-bundle.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            MesCoilSnapshot.__table__,
            MesMaterialRecord.__table__,
            MesStockRecord.__table__,
            MesWorkshopProcessRecord.__table__,
            MesWipTotalSnapshot.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed(db) -> None:
    workshop = Workshop(id=1, code='JZ', name='精整', workshop_type='finishing', sort_order=1, is_active=True)
    machine = Equipment(id=10, code='JZ-01', name='精整1#', workshop_id=1, sort_order=1, is_active=True)
    db.add_all(
        [
            workshop,
            machine,
            MesCoilSnapshot(
                coil_id='MES:feed-1',
                tracking_card_no='feed-1',
                current_workshop='精整',
                feeding_weight=100,
                source_payload={'metadata': {'CreateDate': '2026-06-18 08:00:00', 'CurrentWorkShop': '精整'}},
            ),
            MesWorkshopProcessRecord(
                source_id='proc-1',
                source_path='sqlserver:workshop_process_records',
                workshop_name='精整',
                process_name='包装',
                device_name='精整1#',
                input_weight_tons=98,
                output_weight_tons=88,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 18, 11, 0),
            ),
            MesStockRecord(
                source_id='stock-1',
                source_path='sqlserver:stock_header_records',
                net_weight_tons=85,
                business_date=BUSINESS_DATE,
                in_stock_date=datetime(2026, 6, 18, 12, 0),
            ),
            MesWipTotalSnapshot(
                source_id='wip-1',
                workshop_name='精整',
                process_name='精整',
                doing_count=2,
                doing_weight_tons=12.5,
                snapshot_at=datetime(2026, 6, 18, 12, 10),
                source_payload={
                    'source_page': '调度管理 / 车间实时查询 / 在制料统计',
                    'source_path': '/Dispatch/DoingReportTotal',
                    'source_table': 'MES_Product',
                    'source_weight_field': 'FeedingWeight',
                },
            ),
            MesMaterialRecord(
                source_id='material-hot-used',
                source_path='sqlserver:material_records',
                workshop_name='热轧车间',
                weight_tons=21.5,
                production_date=datetime(2026, 6, 18, 11, 0),
                business_date=BUSINESS_DATE,
                status_name='已使用',
                last_seen_from_mes_at=datetime(2026, 6, 18, 12, 30),
            ),
            MesMaterialRecord(
                source_id='material-hot-unused',
                source_path='sqlserver:material_records',
                workshop_name='热轧车间',
                weight_kg=8500,
                production_date=datetime(2026, 6, 18, 12, 0),
                business_date=BUSINESS_DATE,
                status_name='未使用',
                last_seen_from_mes_at=datetime(2026, 6, 18, 12, 40),
            ),
            MesMaterialRecord(
                source_id='material-hot-void',
                source_path='sqlserver:material_records',
                workshop_name='热轧车间',
                weight_tons=99,
                production_date=datetime(2026, 6, 18, 13, 0),
                business_date=BUSINESS_DATE,
                status_name='作废',
                last_seen_from_mes_at=datetime(2026, 6, 18, 13, 10),
            ),
        ]
    )
    db.commit()


def _fact_by_key(payload: dict, key: str) -> list[dict]:
    return [item for item in payload['facts'] if item['key'] == key]


def _assert_fact_metadata(fact: dict) -> None:
    assert fact['key']
    assert fact['label']
    assert fact['metric_name'] == fact['label']
    assert fact['business_date'] == BUSINESS_DATE.isoformat()
    assert fact['grain']
    assert isinstance(fact['dimensions'], dict)
    assert fact['source']['source_table']
    assert fact['source']['source_fields']
    assert fact['source']['projection_table']
    assert fact['api']
    assert fact['frontend_pages']
    assert fact['hermes_field']
    assert 'status' in fact['sync_status']
    assert fact['updated_at'] is not None or fact['sync_status']
    assert fact['difference_status']
    assert fact['difference_categories']
    assert fact['difference_note']


def test_mes_fact_bundle_exposes_traceable_sources(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed(db)

    with session_factory() as db:
        payload = mes_fact_bundle.build_mes_fact_bundle(db, target_date=BUSINESS_DATE)

    assert payload['read_model']['mode'] == 'sqlserver_adapter_to_local_mes_projection'
    assert payload['business_day']['policy']['default'] == '07:50-07:50'
    assert payload['business_day']['policy']['热轧'] == '10:00-10:00'
    assert payload['business_day']['policy']['owner_daily'] == '09:30'
    assert 'read-through' not in payload['read_model']['decision']
    assert 'debug' in payload

    required_keys = {
        'factory_feeding_daily_input',
        'factory_packaging_daily_output',
        'factory_finished_inbound_daily_output',
        'daily_yield_rate',
        'workshop_feeding_input',
        'workshop_down_machine_output',
        'machine_input_weight',
        'machine_down_machine_output',
        'wip_doing_weight',
        'billet_material_output',
    }
    fact_keys = {item['key'] for item in payload['facts']}
    assert required_keys <= fact_keys
    assert 'follow_card_page_total_feeding' not in fact_keys
    assert 'allocation_packaging_reference' not in fact_keys
    for fact in payload['facts']:
        _assert_fact_metadata(fact)

    feeding = _fact_by_key(payload, 'factory_feeding_daily_input')[0]
    assert feeding['value'] == 100
    assert feeding['source']['source_table'] == 'MES_Product'
    assert feeding['source']['source_fields'] == ['FeedingWeight', 'CreateDate', 'CurrentWorkShop']
    assert feeding['source']['projection_table'] == 'mes_coil_snapshots'
    assert feeding['source']['status'] == '已证实'
    assert 'status' in feeding['sync_status']

    wip = _fact_by_key(payload, 'wip_doing_weight')[0]
    assert wip['value'] == 12.5
    assert wip['source']['source_page'] == '调度管理 / 车间实时查询 / 在制料统计'
    assert wip['source']['source_path'] == '/Dispatch/Index'
    assert wip['source']['projection_table'] == 'mes_wip_total_snapshots'

    billet = _fact_by_key(payload, 'billet_material_output')[0]
    assert billet['value'] == 30
    assert billet['dimensions']['workshop'] == '热轧车间'
    assert billet['dimensions']['row_count'] == 2
    assert billet['source']['source_table'] == 'MES_Material'
    assert billet['source']['source_fields'] == ['Weight', 'ProductionDate', 'WorkShop', 'StatusName=已使用/未使用']
    assert billet['source']['projection_table'] == 'mes_material_records'
    assert billet['source']['status'] == '已证实'

    down_machine = _fact_by_key(payload, 'machine_down_machine_output')[0]
    assert down_machine['value'] == 88
    assert down_machine['source']['source_fields'] == ['DeviceName', 'EndWeight', 'EndDatetime']

    gaps = {item['key']: item['source']['status'] for item in payload['facts']}
    assert 'billet_material_output_rule' not in gaps
    audit_gaps = {item['key']: item['source']['status'] for item in payload['audit_gaps']}
    assert audit_gaps['billet_material_output_rule'] == '已证实'
    assert audit_gaps['follow_card_page_total_feeding'] == '待浏览器/SQL复核'
    assert audit_gaps['allocation_packaging_reference'] == '候选'


def test_template_daily_report_payload_includes_hermes_fact_bundle(monkeypatch) -> None:
    monkeypatch.setattr(
        template_daily_report,
        'build_template_daily_report_facts',
        lambda *_args, **_kwargs: {
            'target_date': BUSINESS_DATE.isoformat(),
            'wip_date': None,
            'values': {'report_date': BUSINESS_DATE.isoformat(), 'total_output_daily': 328.0},
            'sources': {'total_output_daily': {'source_type': 'mes_packaging_output'}},
            'missing_fields': [],
            'conflicts': [],
        },
    )
    monkeypatch.setattr(
        template_daily_report,
        'validate_template_daily_report_facts',
        lambda facts: {'status': 'ready', 'text': '日报正文', 'missing_fields': [], 'conflicts': []},
    )
    monkeypatch.setattr(
        template_daily_report,
        'build_mes_fact_bundle',
        lambda *_args, **_kwargs: {'target_date': BUSINESS_DATE.isoformat(), 'facts': [{'key': 'factory_feeding_daily_input'}]},
    )

    payload = template_daily_report.build_template_daily_report_payload(SimpleNamespace(), target_date=BUSINESS_DATE)

    assert payload['hermes_fact_bundle']['target_date'] == BUSINESS_DATE.isoformat()
    assert payload['hermes_fact_bundle']['facts'][0]['key'] == 'total_output_daily'
    assert payload['hermes_fact_bundle']['facts'][0]['label'] == '车间总产量日合计'
    assert payload['hermes_fact_bundle']['facts'][0]['source']['source_type'] == 'mes_packaging_output'
    assert payload['hermes_fact_bundle']['mes_fact_bundle']['facts'][0]['key'] == 'factory_feeding_daily_input'
    assert 'debug' not in payload['hermes_fact_bundle']['mes_fact_bundle']
    response = TemplateDailyReportPreviewResponse(
        status=payload['status'],
        target_date=BUSINESS_DATE,
        text=payload['text'],
        hermes_fact_bundle=payload['hermes_fact_bundle'],
    )
    assert response.hermes_fact_bundle['facts'][0]['key'] == 'total_output_daily'


def test_mes_fact_bundle_marks_factory_projection_unavailable(monkeypatch, tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed(db)

    monkeypatch.setattr(
        mes_fact_bundle,
        '_safe_factory_production_fact',
        lambda *_args, **_kwargs: {
            'status': 'unavailable',
            'target_date': BUSINESS_DATE.isoformat(),
            'missing_reason': 'factory_projection_missing',
        },
    )

    with session_factory() as db:
        payload = mes_fact_bundle.build_mes_fact_bundle(db, target_date=BUSINESS_DATE)

    for key in (
        'factory_feeding_daily_input',
        'factory_packaging_daily_output',
        'factory_finished_inbound_daily_output',
        'daily_yield_rate',
    ):
        fact = _fact_by_key(payload, key)[0]
        assert fact['value'] is None
        assert fact['source']['status'] == '不可用'
        assert fact['status'] == '不可用'
        assert fact['missing_reason'] == 'factory_projection_missing'
        assert fact['difference_status'] == 'source_unavailable'


def test_mes_fact_bundle_does_not_swallow_unexpected_sync_errors(monkeypatch, tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed(db)

    def raise_unexpected(_db):
        raise RuntimeError('unexpected sync bug')

    monkeypatch.setattr(mes_fact_bundle.mes_sync_service, 'latest_sync_status', raise_unexpected)

    with session_factory() as db, pytest.raises(RuntimeError, match='unexpected sync bug'):
        mes_fact_bundle.build_mes_fact_bundle(db, target_date=BUSINESS_DATE)


def test_mes_fact_bundle_route_returns_manager_payload(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed(db)

    def fake_get_db():
        with session_factory() as db:
            yield db

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

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_manager_user] = fake_get_user
    try:
        response = TestClient(app).get('/api/v1/dashboard/mes-fact-bundle', params={'target_date': '2026-06-18'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['target_date'] == '2026-06-18'
    assert payload['read_model']['mode'] == 'sqlserver_adapter_to_local_mes_projection'
    assert any(item['key'] == 'wip_doing_weight' for item in payload['facts'])
