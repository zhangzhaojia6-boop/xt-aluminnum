from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.mes import (
    MesMaterialRecord,
    MesReferenceItem,
    MesStockRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
    MesYieldRecord,
)
from app.services import mes_extended_service


def _manager_user():
    return SimpleNamespace(
        id=1,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        data_scope_type='all',
    )


def _mobile_user():
    return SimpleNamespace(
        id=2,
        role='machine_operator',
        is_admin=False,
        is_manager=False,
        is_reviewer=False,
        data_scope_type='self_workshop',
    )


def _dummy_db():
    yield SimpleNamespace()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_mes_extended_summary_route(monkeypatch):
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_current_user] = _manager_user
    monkeypatch.setattr(
        'app.routers.mes.mes_extended_service.build_summary',
        lambda db, **_kwargs: {
            'sources': [
                {
                    'key': 'workshop_process_records',
                    'label': '车间过站',
                    'row_count': 2,
                    'status': 'ready',
                    'latest_business_date': date(2026, 5, 31),
                    'latest_seen_at': datetime(2026, 6, 1, 1, 30, tzinfo=UTC),
                }
            ]
        },
    )

    response = TestClient(app).get('/api/v1/mes/extended/summary')

    assert response.status_code == 200
    payload = response.json()
    assert payload['sources'][0]['key'] == 'workshop_process_records'
    assert payload['sources'][0]['row_count'] == 2
    assert payload['sources'][0]['status'] == 'ready'


def test_mes_extended_routes_reject_mobile_user(monkeypatch):
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_current_user] = _mobile_user
    monkeypatch.setattr('app.routers.mes.mes_extended_service.build_summary', lambda db, **_kwargs: {'sources': []})

    response = TestClient(app).get('/api/v1/mes/extended/summary')

    assert response.status_code == 403


def test_mes_extended_workshop_process_route_passes_filters(monkeypatch):
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_current_user] = _manager_user
    seen = {}

    def fake_records(_db, *, business_date=None, search=None, limit=100, offset=0, workshop_names=None):
        seen.update({'business_date': business_date, 'search': search, 'limit': limit, 'offset': offset, 'workshop_names': workshop_names})
        return [
            {
                'source_id': 'process-1',
                'batch_no': '26RA001',
                'customer_alias': '华东客户',
                'workshop_name': '在线退火分厂',
                'process_name': '退火',
                'worker_name': '张三',
                'device_name': '1#退火炉',
                'input_weight_tons': 4.6,
                'output_weight_tons': 4.42,
                'yield_rate': 96.08,
                'end_time': datetime(2026, 5, 31, 23, 10, tzinfo=UTC),
                'business_date': date(2026, 5, 31),
                'last_seen_from_mes_at': datetime(2026, 6, 1, 1, 30, tzinfo=UTC),
            }
        ]

    monkeypatch.setattr('app.routers.mes.mes_extended_service.list_workshop_process_records', fake_records)
    monkeypatch.setattr('app.routers.mes.mes_extended_service.resolve_workshop_id_names', lambda _db, workshop_id: {'新厂在线车间'} if workshop_id == 20 else set())

    response = TestClient(app).get(
        '/api/v1/mes/extended/workshop-process-records',
        params={'business_date': '2026-05-31', 'workshop_id': 20, 'search': '26RA', 'limit': 20, 'offset': 10},
    )

    assert response.status_code == 200
    assert response.json()[0]['source_id'] == 'process-1'
    assert seen == {
        'business_date': date(2026, 5, 31),
        'search': '26RA',
        'limit': 20,
        'offset': 10,
        'workshop_names': {'新厂在线车间'},
    }


def test_mes_extended_workshop_process_route_denies_cross_workshop(monkeypatch):
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=9,
        role='workshop_director',
        is_admin=False,
        is_manager=True,
        is_reviewer=True,
        workshop_id=20,
        data_scope_type='self_workshop',
    )
    monkeypatch.setattr('app.routers.mes.mes_extended_service.list_workshop_process_records', lambda *_args, **_kwargs: [])

    response = TestClient(app).get(
        '/api/v1/mes/extended/workshop-process-records',
        params={'business_date': '2026-05-31', 'workshop_id': 21},
    )

    assert response.status_code == 403


def test_mes_extended_wip_total_route_passes_business_date(monkeypatch):
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_current_user] = _manager_user
    seen = {}

    def fake_wip(_db, *, business_date=None, search=None, limit=100, offset=0, workshop_names=None):
        seen.update({'business_date': business_date, 'search': search, 'limit': limit, 'offset': offset, 'workshop_names': workshop_names})
        return [
            {
                'source_id': 'wip-1',
                'workshop_name': '在线退火分厂',
                'process_name': '退火',
                'doing_count': 3,
                'doing_weight_tons': 12.5,
                'snapshot_at': datetime(2026, 5, 31, 15, 35, tzinfo=UTC),
            }
        ]

    monkeypatch.setattr('app.routers.mes.mes_extended_service.list_wip_total_snapshots', fake_wip)

    response = TestClient(app).get(
        '/api/v1/mes/extended/wip-total-snapshots',
        params={'business_date': '2026-05-31', 'search': '退火', 'limit': 20, 'offset': 10},
    )

    assert response.status_code == 200
    assert response.json()[0]['source_id'] == 'wip-1'
    assert seen == {
        'business_date': date(2026, 5, 31),
        'search': '退火',
        'limit': 20,
        'offset': 10,
        'workshop_names': None,
    }


def test_mes_extended_reference_items_route_passes_filters(monkeypatch):
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_current_user] = _manager_user
    seen = {}

    def fake_items(_db, *, source_type=None, search=None, limit=100, offset=0, workshop_names=None):
        seen.update({'source_type': source_type, 'search': search, 'limit': limit, 'offset': offset})
        return [
            {
                'source_type': 'customer',
                'source_id': 'customer-1',
                'code': 'C001',
                'name': '华东客户',
                'parent_id': None,
                'workshop_name': None,
                'status_name': '启用',
                'last_seen_from_mes_at': datetime(2026, 6, 1, 1, 34, tzinfo=UTC),
            }
        ]

    monkeypatch.setattr('app.routers.mes.mes_extended_service.list_reference_items', fake_items)

    response = TestClient(app).get(
        '/api/v1/mes/extended/reference-items',
        params={'source_type': 'customer', 'search': '华东', 'limit': 30, 'offset': 5},
    )

    assert response.status_code == 200
    assert response.json()[0]['name'] == '华东客户'
    assert seen == {'source_type': 'customer', 'search': '华东', 'limit': 30, 'offset': 5}


def test_mes_extended_service_summarizes_and_filters_without_raw_payload(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-extended.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            MesWorkshopProcessRecord.__table__,
            MesStockRecord.__table__,
            MesMaterialRecord.__table__,
            MesYieldRecord.__table__,
            MesReferenceItem.__table__,
            MesWipTotalSnapshot.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, future=True)

    with Session() as db:
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id='process-1',
                    source_path='/WorkShopManage/GetFinishPartCardList',
                    batch_no='26RA001',
                    customer_alias='华东客户',
                    workshop_name='在线退火分厂',
                    process_name='退火',
                    worker_name='张三',
                    device_name='1#退火炉',
                    input_weight_tons=4.6,
                    output_weight_tons=4.42,
                    yield_rate=96.08,
                    end_time=datetime(2026, 5, 31, 23, 10, tzinfo=UTC),
                    business_date=date(2026, 5, 31),
                    last_seen_from_mes_at=datetime(2026, 6, 1, 1, 30, tzinfo=UTC),
                    source_payload={'Password': 'secret', 'BatchNo': '26RA001'},
                ),
                MesWorkshopProcessRecord(
                    source_id='process-2',
                    source_path='/WorkShopManage/GetFinishPartCardList',
                    batch_no='26RB999',
                    workshop_name='冷轧',
                    process_name='轧制',
                    business_date=date(2026, 5, 30),
                    last_seen_from_mes_at=datetime(2026, 5, 30, 9, 0, tzinfo=UTC),
                ),
                MesStockRecord(
                    source_id='stock-1',
                    source_path='/Stock/GetStockList',
                    batch_no='26RA001',
                    contract_no='HT-1',
                    customer_alias='华东客户',
                    net_weight_tons=4.4,
                    business_date=date(2026, 5, 31),
                    last_seen_from_mes_at=datetime(2026, 6, 1, 1, 31, tzinfo=UTC),
                ),
                MesMaterialRecord(
                    source_id='material-1',
                    source_path='/Material/GetMaterialList',
                    material_code='AL-1',
                    workshop_name='在线退火分厂',
                    line_name='1#退火炉',
                    weight_tons=4.5,
                    business_date=date(2026, 5, 31),
                    last_seen_from_mes_at=datetime(2026, 6, 1, 1, 32, tzinfo=UTC),
                ),
                MesYieldRecord(
                    source_id='yield-1',
                    source_path='/Report/GetYieldRate',
                    batch_no='26RA001',
                    contract_no='HT-1',
                    yield_rate=96.08,
                    business_date=date(2026, 5, 31),
                    last_seen_from_mes_at=datetime(2026, 6, 1, 1, 33, tzinfo=UTC),
                ),
                MesReferenceItem(
                    source_type='customer',
                    source_id='customer-1',
                    source_path='/Customer/GetList',
                    name='华东客户',
                    last_seen_from_mes_at=datetime(2026, 6, 1, 1, 34, tzinfo=UTC),
                ),
                MesWipTotalSnapshot(
                    source_id='wip-1',
                    workshop_name='在线退火分厂',
                    process_name='退火',
                    doing_count=3,
                    doing_weight_tons=12500.0,
                    snapshot_at=datetime(2026, 5, 31, 15, 35, tzinfo=UTC),
                    source_payload={'Password': 'secret'},
                ),
                MesWipTotalSnapshot(
                    source_id='wip-old',
                    workshop_name='在线退火分厂',
                    process_name='退火',
                    doing_count=9,
                    doing_weight_tons=99.0,
                    snapshot_at=datetime(2026, 5, 30, 23, 0, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

        summary = mes_extended_service.build_summary(db)
        records = mes_extended_service.list_workshop_process_records(
            db,
            business_date=date(2026, 5, 31),
            search='华东',
            limit=10,
            offset=0,
        )
        stock_rows = mes_extended_service.list_stock_records(db, business_date=date(2026, 5, 31), search='HT-1')
        material_rows = mes_extended_service.list_material_records(db, business_date=date(2026, 5, 31), search='AL-1')
        yield_rows = mes_extended_service.list_yield_records(db, business_date=date(2026, 5, 31), search='26RA')
        reference_rows = mes_extended_service.list_reference_items(db, source_type='customer', search='华东')
        wip_rows = mes_extended_service.list_wip_total_snapshots(db, business_date=date(2026, 5, 31), search='退火')
        fallback_wip_rows = mes_extended_service.list_wip_total_snapshots(db, business_date=date(2026, 5, 29), search='退火')

    summary_by_key = {item['key']: item for item in summary['sources']}
    assert summary_by_key['workshop_process_records']['row_count'] == 2
    assert summary_by_key['workshop_process_records']['latest_business_date'] == date(2026, 5, 31)
    assert summary_by_key['stock_records']['row_count'] == 1
    assert summary_by_key['wip_total_snapshots']['row_count'] == 2
    assert records == [
        {
            'source_id': 'process-1',
            'batch_no': '26RA001',
            'customer_alias': '华东客户',
            'workshop_name': '在线退火分厂',
            'process_name': '退火',
            'worker_name': '张三',
            'device_name': '1#退火炉',
            'input_weight_tons': 4.6,
            'output_weight_tons': 4.42,
            'yield_rate': 96.08,
            'end_time': datetime(2026, 5, 31, 23, 10, tzinfo=UTC),
            'business_date': date(2026, 5, 31),
            'last_seen_from_mes_at': datetime(2026, 6, 1, 1, 30, tzinfo=UTC),
        }
    ]
    assert 'source_payload' not in records[0]
    assert stock_rows[0]['source_id'] == 'stock-1'
    assert 'source_payload' not in stock_rows[0]
    assert material_rows[0]['source_id'] == 'material-1'
    assert 'source_payload' not in material_rows[0]
    assert yield_rows[0]['source_id'] == 'yield-1'
    assert 'source_payload' not in yield_rows[0]
    assert reference_rows[0]['source_id'] == 'customer-1'
    assert 'source_payload' not in reference_rows[0]
    assert len(wip_rows) == 1
    assert wip_rows[0]['workshop_name'] == '在线退火分厂'
    assert wip_rows[0]['source_id'] == 'wip-1'
    assert wip_rows[0]['doing_weight_tons'] == 12.5
    assert wip_rows[0]['source_page'] == '调度管理 / 车间实时查询 / 在制料统计'
    assert wip_rows[0]['source_table'] == 'MES_Product'
    assert wip_rows[0]['source_weight_field'] == 'FeedingWeight'
    assert 'source_payload' not in wip_rows[0]
    assert fallback_wip_rows == []
