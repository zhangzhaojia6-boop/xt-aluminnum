from datetime import datetime

import pytest

from app.adapters.sqlserver_mes_adapter import SqlServerMesAdapter, _QUERY_BY_KEY, _ensure_read_only_query


class _QueryRunner:
    def __init__(self, rows_by_key):
        self.rows_by_key = rows_by_key
        self.calls = []

    def __call__(self, query_key, *, limit=200, tracking_card_no=None):
        self.calls.append((query_key, limit, tracking_card_no))
        return list(self.rows_by_key.get(query_key, []))


def test_sqlserver_adapter_maps_dispatch_rows_to_coil_snapshots() -> None:
    runner = _QueryRunner({
        'dispatch': [
            {
                'ProductId': 8842,
                'TrackingCardNo': 'S-2-085-2',
                'BatchNo': '26RA04597',
                'ContractNo': 'HT-01',
                'CustomerName': '华东客户',
                'AlloyGrade': '3003',
                'MaterialState': 'H24',
                'Spec': '0.72*1220*C',
                'SpecThickness': '0.72',
                'SpecWidth': '1220',
                'FeedingWeight': '12.4',
                'MaterialWeight': '12.1',
                'CurrentWorkShop': '冷轧',
                'CurrentProcess': '轧制',
                'CurrentProcessSort': '20',
                'NextWorkShop': '退火',
                'NextProcess': '退火',
                'ProcessRoute': '铸轧-冷轧-退火',
                'PrintProcessRoute': '铸轧 > 冷轧 > 退火',
                'StatusName': '生产中',
                'UpdateTime': '2026-06-04 08:30:00',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_dispatch(limit=50)

    assert len(rows) == 1
    row = rows[0]
    assert row.coil_id == 'MES:8842'
    assert row.tracking_card_no == 'S-2-085-2'
    assert row.batch_no == '26RA04597'
    assert row.contract_no == 'HT-01'
    assert row.workshop_code == '冷轧'
    assert row.process_code == '轧制'
    assert row.status == '生产中'
    assert row.updated_at == datetime(2026, 6, 4, 8, 30)
    assert row.metadata['CustomerName'] == '华东客户'
    assert row.metadata['AlloyGrade'] == '3003'
    assert row.metadata['Spec'] == '0.72*1220*C'
    assert row.metadata['CurrentProcessSort'] == 20
    assert runner.calls == [('dispatch', 50, None)]


def test_sqlserver_adapter_maps_real_xtal_product_rows_to_coil_snapshots() -> None:
    runner = _QueryRunner({
        'dispatch': [
            {
                'Id': 'product-1',
                'MaterialCode': '26-A-1-001-1',
                'PBatchNumber': 'PB-01',
                'ContractCode': 'HT-01',
                'Customer': '客户A',
                'Alloy': '3003',
                'Specification': '0.72*1220*C',
                'CurrentWorkShop': '2050车间',
                'CurrentProcess': '冷轧',
                'NextWorkShop': '园区在线车间',
                'NextProcess': '在线退火',
                'ProcessRoute': '2050车间(冷轧)-园区在线车间(在线退火)',
                'Status': 1,
                'OperateDate': '2026-06-04 08:30:00',
            }
        ],
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_dispatch(limit=20)

    assert len(rows) == 1
    row = rows[0]
    assert row.coil_id == 'MES:product-1'
    assert row.tracking_card_no == '26-A-1-001-1'
    assert row.batch_no == 'PB-01'
    assert row.contract_no == 'HT-01'
    assert row.workshop_code == '2050车间'
    assert row.process_code == '冷轧'
    assert row.updated_at == datetime(2026, 6, 4, 8, 30)
    assert row.metadata['Customer'] == '客户A'
    assert row.metadata['Alloy'] == '3003'
    assert row.metadata['Specification'] == '0.72*1220*C'


def test_sqlserver_adapter_get_tracking_card_info_uses_dispatch_rows() -> None:
    runner = _QueryRunner({
        'card_lookup': [
            {
                'ProductId': 9001,
                'TrackingCardNo': 'S-2-085-2',
                'BatchNo': '26RA04597',
                'AlloyGrade': '3003',
                'ProcessRoute': '铸轧-冷轧-退火',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    card = adapter.get_tracking_card_info('S一2一085一2')

    assert card is not None
    assert card.card_no == 'S-2-085-2'
    assert card.alloy_grade == '3003'
    assert card.batch_no == '26RA04597'
    assert card.process_route_code == '铸轧-冷轧-退火'
    assert runner.calls == [('card_lookup', 1, 'S-2-085-2')]


def test_sqlserver_adapter_get_tracking_card_info_falls_back_to_recent_dispatch_rows() -> None:
    runner = _QueryRunner({
        'card_lookup': [],
        'dispatch': [
            {
                'ProductId': 9001,
                'TrackingCardNo': 'S-2-085-2',
                'BatchNo': '26RA04597',
                'AlloyGrade': '3003',
            }
        ],
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    card = adapter.get_tracking_card_info('S一2一085一2')

    assert card is not None
    assert card.card_no == 'S-2-085-2'
    assert runner.calls == [('card_lookup', 1, 'S-2-085-2'), ('dispatch', 200, None)]


def test_sqlserver_adapter_maps_wip_totals() -> None:
    runner = _QueryRunner({
        'wip_totals': [
            {
                'WorkShopName': '冷轧',
                'ProcessName': '轧制',
                'DoingCount': '8',
                'DoingWeight': '25.5',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_wip_totals()

    assert len(rows) == 1
    assert rows[0].workshop_name == '冷轧'
    assert rows[0].doing_count == 8
    assert rows[0].doing_weight == 25.5
    assert rows[0].metadata['ProcessName'] == '轧制'
    assert rows[0].metadata['process_totals'] == {'轧制': 25.5}


def test_sqlserver_adapter_maps_stock_record_event_time_from_allocation_date_before_create_date() -> None:
    runner = _QueryRunner({
        'stock_records': [
            {
                'Id': 'stock-1',
                'BatchNumber': 'PB-001',
                'NetWeight': '1200',
                'AllocationDate': '2026-06-03 16:30:00',
                'CreateDate': '2026-06-04 08:30:00',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_stock_records(limit=10)

    assert len(rows) == 1
    assert rows[0].event_time == datetime(2026, 6, 3, 16, 30)
    assert rows[0].metadata['AllocationDate'] == '2026-06-03 16:30:00'
    assert rows[0].metadata['CreateDate'] == '2026-06-04 08:30:00'


def test_sqlserver_query_guard_allows_select_only() -> None:
    _ensure_read_only_query('SELECT TOP (10) * FROM v_CoilStatus')
    _ensure_read_only_query('  select DB_NAME() AS database_name')
    _ensure_read_only_query('SELECT\n  DB_NAME() AS database_name')
    _ensure_read_only_query("SELECT HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE') AS can_update")


@pytest.mark.parametrize(
    'query',
    [
        'UPDATE dbo.Product SET Name = Name',
        'SELECT * FROM v_CoilStatus; DELETE FROM dbo.Product',
        'EXEC dbo.RefreshProduct',
        'DROP TABLE dbo.Product',
    ],
)
def test_sqlserver_query_guard_rejects_write_or_stacked_sql(query: str) -> None:
    with pytest.raises(ValueError):
        _ensure_read_only_query(query)


def test_sqlserver_default_queries_target_discovered_xtal_tables() -> None:
    assert 'MES_Product' in _QUERY_BY_KEY['dispatch']
    assert 'MES_Product' in _QUERY_BY_KEY['card_lookup']
    assert 'MES_Product' in _QUERY_BY_KEY['wip_totals']
    assert 'MES_ProductProcessRecord' in _QUERY_BY_KEY['workshop_process_records']
    assert 'ORDER BY EndDatetime DESC' in _QUERY_BY_KEY['workshop_process_records']
    assert 'ORDER BY AllocationDate DESC' in _QUERY_BY_KEY['stock_records']
    assert "CurrentWorkShop IS NOT NULL" in _QUERY_BY_KEY['wip_totals']
    assert "CurrentProcess IS NOT NULL" in _QUERY_BY_KEY['wip_totals']
    assert 'SUM(FeedingWeight)' in _QUERY_BY_KEY['wip_totals']
    assert 'WMS_Stock' in _QUERY_BY_KEY['stock']
    assert all('v_CoilStatus' not in query for query in _QUERY_BY_KEY.values())
