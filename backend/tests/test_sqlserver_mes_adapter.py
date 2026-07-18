from datetime import datetime

import pytest

from app.adapters.sqlserver_mes_adapter import (
    MesReadOnlyViolation,
    SQLSERVER_QUERY_SPECS,
    SqlServerMesAdapter,
    _BETWEEN_QUERY_BY_KEY,
    _QUERY_BY_KEY,
    _ensure_read_only_query,
    audit_sqlserver_readonly_contract,
    classify_sqlserver_failure,
)


class _QueryRunner:
    def __init__(self, rows_by_key):
        self.rows_by_key = rows_by_key
        self.calls = []

    def __call__(self, query_key, *, limit=200, tracking_card_no=None, offset=0, start_at=None, end_at=None):
        self.calls.append((query_key, limit, tracking_card_no, offset, start_at, end_at))
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
    assert runner.calls == [('dispatch', 50, None, 0, None, None)]


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
    assert runner.calls == [('card_lookup', 1, 'S-2-085-2', 0, None, None)]


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
    assert runner.calls == [('card_lookup', 1, 'S-2-085-2', 0, None, None), ('dispatch', 200, None, 0, None, None)]


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


def test_sqlserver_adapter_maps_stock_record_event_time_from_create_date_before_allocation_date() -> None:
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
    assert rows[0].event_time == datetime(2026, 6, 4, 8, 30)
    assert rows[0].metadata['AllocationDate'] == '2026-06-03 16:30:00'
    assert rows[0].metadata['CreateDate'] == '2026-06-04 08:30:00'


def test_sqlserver_adapter_maps_finished_inbound_header_between() -> None:
    start_at = datetime(2026, 6, 17, 7, 30)
    end_at = datetime(2026, 6, 18, 7, 30)
    runner = _QueryRunner({
        'finished_inbound_records': [
            {
                'Id': 'inbound-1',
                'FromDepartment': '园区精整',
                'ToDepartment': '成品库',
                'TotalNetWeight': '303031',
                'InStockDate': '2026-06-17 09:10:00',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_finished_inbound_records_between(start_at=start_at, end_at=end_at, limit=1000, offset=2000)

    assert len(rows) == 1
    assert rows[0].source_id == 'stock_header_records:inbound-1'
    assert rows[0].source_path == 'sqlserver:stock_header_records'
    assert rows[0].event_time == datetime(2026, 6, 17, 9, 10)
    assert rows[0].metadata['TotalNetWeight'] == '303031'
    assert runner.calls == [('finished_inbound_records', 1000, None, 2000, start_at, end_at)]


def test_sqlserver_adapter_maps_delivery_records_between() -> None:
    start_at = datetime(2026, 6, 17, 7, 30)
    end_at = datetime(2026, 6, 18, 7, 30)
    runner = _QueryRunner({
        'delivery_records': [
            {
                'Id': 'delivery-1',
                'DeliveryCode': 'FH-1',
                'NetWeight': '222306',
                'OperateDate': '2026-06-17 14:20:00',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_delivery_records_between(start_at=start_at, end_at=end_at, limit=500, offset=0)

    assert len(rows) == 1
    assert rows[0].source_id == 'delivery_records:delivery-1'
    assert rows[0].source_path == 'sqlserver:delivery_records'
    assert rows[0].event_time == datetime(2026, 6, 17, 14, 20)


def test_sqlserver_adapter_falls_back_to_wms_outstock_delivery_records_between() -> None:
    start_at = datetime(2026, 6, 17, 7, 30)
    end_at = datetime(2026, 6, 18, 7, 30)
    runner = _QueryRunner({
        'delivery_records': [],
        'delivery_stock_records': [
            {
                'Id': 'outstock-1',
                'DeliveryCode': 'FH-2',
                'NetWeight': '222306',
                'CreateDate': '2026-06-17 15:20:00',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_delivery_records_between(start_at=start_at, end_at=end_at, limit=500, offset=0)

    assert len(rows) == 1
    assert rows[0].source_id == 'delivery_stock_records:outstock-1'
    assert rows[0].source_path == 'sqlserver:delivery_stock_records'
    assert rows[0].event_time == datetime(2026, 6, 17, 15, 20)


def test_sqlserver_adapter_maps_material_record_event_time_from_production_date() -> None:
    runner = _QueryRunner({
        'material_records': [
            {
                'Id': 'material-1',
                'MaterialCode': 'R4-8998-2',
                'WorkShopRolling': '热轧车间',
                'WorkShopLine': '1#',
                'Weight': '7830',
                'ProductionDate': '2026-06-17 04:25:00',
                'CreateDate': '2026-06-17 08:57:59',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_material_records(limit=10)

    assert len(rows) == 1
    assert rows[0].event_time == datetime(2026, 6, 17, 4, 25)
    assert rows[0].metadata['WorkShopRolling'] == '热轧车间'
    assert rows[0].metadata['WorkShopLine'] == '1#'


def test_sqlserver_adapter_maps_xtal_device_workshop_to_machine_line() -> None:
    runner = _QueryRunner({
        'devices': [
            {
                'Id': 'device-1',
                'Name': '园区北线（WIFI）',
                'WorkShop': '园区在线车间',
                'Craft': '在线退火',
            }
        ]
    })
    adapter = SqlServerMesAdapter(query_runner=runner)

    rows = adapter.list_machine_line_sources()

    assert len(rows) == 1
    assert rows[0].line_code == 'device-1'
    assert rows[0].line_name == '园区北线（WIFI）'
    assert rows[0].workshop_name == '园区在线车间'


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
        'SELECT * INTO dbo.CoilStatusCopy FROM v_CoilStatus',
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
    assert 'MES_Material' in _QUERY_BY_KEY['material_records']
    assert 'MES_Feeding' not in _QUERY_BY_KEY['material_records']
    assert 'ORDER BY EndDatetime DESC' in _QUERY_BY_KEY['workshop_process_records']
    assert 'ORDER BY ProductionDate DESC' in _QUERY_BY_KEY['material_records']
    assert 'ORDER BY CreateDate DESC' in _QUERY_BY_KEY['stock_records']
    assert "CurrentWorkShop IS NOT NULL" in _QUERY_BY_KEY['wip_totals']
    assert "CurrentProcess IS NOT NULL" in _QUERY_BY_KEY['wip_totals']
    assert 'SUM(FeedingWeight)' in _QUERY_BY_KEY['wip_totals']
    assert 'WMS_Stock' in _QUERY_BY_KEY['stock']
    assert all('v_CoilStatus' not in query for query in _QUERY_BY_KEY.values())


def test_all_registered_sqlserver_queries_are_select_only() -> None:
    audit = audit_sqlserver_readonly_contract()

    assert audit['status'] == 'pass'
    assert audit['passed'] is True
    assert audit['issues'] == []
    assert audit['query_count'] == len(_QUERY_BY_KEY) + len(_BETWEEN_QUERY_BY_KEY) + 2
    assert len(audit['contract_sha256']) == 64
    assert len({spec.probe_id for spec in SQLSERVER_QUERY_SPECS}) == len(SQLSERVER_QUERY_SPECS)


def test_sqlserver_adapter_rejects_completion_writes() -> None:
    adapter = SqlServerMesAdapter(query_runner=_QueryRunner({}))

    assert adapter.readonly is True
    with pytest.raises(MesReadOnlyViolation, match='mes_sqlserver_read_only'):
        adapter.push_completion('CARD-1', 1.0, 99.0)


@pytest.mark.parametrize(
    ('error', 'expected'),
    [
        (ConnectionError('server unavailable'), 'connection_failed'),
        (TimeoutError('query timed out'), 'query_timeout'),
        (RuntimeError("Invalid column name 'OperateDate'"), 'schema_changed'),
        (RuntimeError('unexpected read failure'), 'read_failed'),
    ],
)
def test_sqlserver_failure_classification_is_stable(error: Exception, expected: str) -> None:
    assert classify_sqlserver_failure(error) == expected
