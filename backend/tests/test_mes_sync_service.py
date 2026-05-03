from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.adapters.mes_adapter import CoilSnapshot, MesMachineLineSource
from app.services import mes_sync_service


class _FakeQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._value


class _FakeDB:
    def __init__(self):
        self.added = []
        self.cursor = None
        self.snapshot = None
        self.deleted = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None

    def delete(self, value):
        self.deleted.append(value)

    def query(self, model):
        if model is mes_sync_service.MesSyncCursor:
            return _FakeQuery(self.cursor)
        if model is mes_sync_service.MesCoilSnapshot:
            return _FakeQuery(self.snapshot)
        if hasattr(mes_sync_service, 'MesMachineLineSnapshot') and model is mes_sync_service.MesMachineLineSnapshot:
            return _FakeQuery(None)
        if hasattr(mes_sync_service, 'CoilFlowEvent') and model is mes_sync_service.CoilFlowEvent:
            return _FakeQuery(None)
        if model is mes_sync_service.MesSyncRunLog:
            return _FakeQuery(None)
        raise AssertionError(model)


def test_sync_coil_snapshots_updates_cursor_and_stats(monkeypatch):
    db = _FakeDB()
    cursor = SimpleNamespace(cursor_key='coil_snapshots', cursor_value='cursor-1', last_event_at=None, last_synced_at=None, window_started_at=None)
    db.cursor = cursor
    snapshot = CoilSnapshot(
        coil_id='coil-1',
        tracking_card_no='RA260001',
        workshop_code='ZR2',
        process_code='casting',
        machine_code='ZD-1',
        shift_code='A',
        status='in_progress',
        updated_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC),
    )

    monkeypatch.setattr('app.services.mes_sync_service._ensure_cursor', lambda _db, *, cursor_key: cursor)
    monkeypatch.setattr('app.services.mes_sync_service._upsert_snapshot', lambda _db, *, snapshot, synced_at: (True, False))
    monkeypatch.setattr(
        'app.services.mes_sync_service.get_mes_adapter',
        lambda: SimpleNamespace(list_coil_snapshots=lambda **kwargs: ([snapshot], 'cursor-2')),
    )

    payload = mes_sync_service.sync_coil_snapshots(db, now=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))

    assert payload.status == 'success'
    assert payload.fetched_count == 1
    assert payload.upserted_count == 1
    assert payload.next_cursor == 'cursor-2'
    assert cursor.cursor_value == 'cursor-2'


def test_upsert_snapshot_projects_mvc_fields_and_prefers_mes_product_id():
    db = _FakeDB()
    snapshot = CoilSnapshot(
        coil_id='vendor-row-1',
        tracking_card_no='BN-2601',
        batch_no='BN-2601',
        status='running',
        updated_at=datetime(2026, 5, 2, 8, 30, tzinfo=UTC),
        metadata={
            'Product': {'Id': 8842},
            'MaterialCode': '3003-H24',
            'CustomerSimple': '华东客户',
            'Alloy': '3003',
            'State': 'H24',
            'SpecThickness': '0.72',
            'SpecWidth': '1220',
            'SpecLength': 'C',
            'Specification': '0.72*1220*C',
            'FeedingWeight': '12.4',
            'MaterialWeight': '12.1',
            'GrossWeight': '12.0',
            'NetWeight': '11.8',
            'CurrentWorkShop': '冷轧',
            'CurrentProcess': '轧制',
            'CurrentProcessSort': '20',
            'NextWorkShop': '退火',
            'NextProcess': '退火',
            'NextProcessSort': '30',
            'ProcessRoute': '铸轧-冷轧-退火',
            'PrintProcessRoute': '铸轧 > 冷轧 > 退火',
            'StatusName': '生产中',
            'CardStatusName': '已排产',
            'ProductionStatus': 'doing',
            'DelayHour': '2.5',
            'InStockDate': '/Date(1777795200000)/',
            'DeliveryDate': '2026-05-04T08:00:00Z',
            'AllocationDate': '2026-05-05T08:00:00Z',
        },
    )

    changed, replayed = mes_sync_service._upsert_snapshot(
        db,
        snapshot=snapshot,
        synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC),
    )

    assert changed is True
    assert replayed is False
    entity = next(item for item in db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert entity.coil_id == 'MES:8842'
    assert entity.mes_product_id == '8842'
    assert entity.material_code == '3003-H24'
    assert entity.customer_alias == '华东客户'
    assert entity.alloy_grade == '3003'
    assert entity.material_state == 'H24'
    assert entity.spec_display == '0.72*1220*C'
    assert entity.current_workshop == '冷轧'
    assert entity.current_process == '轧制'
    assert entity.current_process_sort == 20
    assert entity.next_workshop == '退火'
    assert entity.next_process == '退火'
    assert entity.next_process_sort == 30
    assert entity.process_route_text == '铸轧-冷轧-退火'
    assert entity.print_process_route_text == '铸轧 > 冷轧 > 退火'
    assert entity.status_name == '生产中'
    assert entity.delay_hours == 2.5
    assert entity.in_stock_date is not None
    assert entity.last_seen_from_mes_at == datetime(2026, 5, 2, 8, 35, tzinfo=UTC)


def test_upsert_snapshot_uses_fallback_key_without_product_id():
    db = _FakeDB()
    snapshot = CoilSnapshot(
        coil_id='',
        tracking_card_no='BN-2602',
        batch_no='BN-2602',
        metadata={'MaterialCode': '5052-O'},
    )

    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC))

    entity = next(item for item in db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert entity.coil_id == 'fallback:BN-2602:5052-O'


def test_sync_machine_lines_maps_device_slots_to_stable_line_codes(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(
        'app.services.mes_sync_service.get_mes_adapter',
        lambda: SimpleNamespace(
            list_machine_line_sources=lambda: [
                MesMachineLineSource(line_code='', line_name='1#轧机', workshop_name='冷轧'),
                MesMachineLineSource(line_code='', line_name='11#拉弯矫', workshop_name='精整'),
            ]
        ),
    )

    stats = mes_sync_service.sync_mes_machine_lines(db, now=datetime(2026, 5, 2, 8, 35, tzinfo=UTC))

    rows = [item for item in db.added if item.__class__.__name__ == 'MesMachineLineSnapshot']
    assert stats.fetched_count == 2
    assert stats.upserted_count == 2
    assert rows[0].line_code == '冷轧:01'
    assert rows[1].line_code == '精整:11'


def test_upsert_snapshot_writes_flow_events_idempotently_for_process_changes():
    existing = SimpleNamespace(
        coil_id='MES:8842',
        tracking_card_no='BN-2601',
        qr_code=None,
        batch_no='BN-2601',
        contract_no=None,
        workshop_code=None,
        process_code='轧制',
        machine_code=None,
        shift_code=None,
        status='running',
        business_date=None,
        event_time=None,
        updated_from_mes_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        last_synced_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        source_payload={},
        current_workshop='冷轧',
        current_process='轧制',
        next_workshop='退火',
        next_process='退火',
    )
    db = _FakeDB()
    db.snapshot = existing
    snapshot = CoilSnapshot(
        coil_id='MES:8842',
        tracking_card_no='BN-2601',
        batch_no='BN-2601',
        process_code='退火',
        metadata={
            'Product': {'Id': 8842},
            'CurrentWorkShop': '退火',
            'CurrentProcess': '退火',
            'NextWorkShop': '精整',
            'NextProcess': '拉弯矫',
        },
        updated_at=datetime(2026, 5, 2, 8, 30, tzinfo=UTC),
    )

    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC))
    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 5, 2, 8, 36, tzinfo=UTC))

    events = [item for item in db.added if item.__class__.__name__ == 'CoilFlowEvent']
    assert len(events) == 1
    assert events[0].coil_key == 'MES:8842'
    assert events[0].previous_process == '轧制'
    assert events[0].current_process == '退火'
    assert events[0].next_process == '拉弯矫'


def test_sync_coil_snapshots_marks_run_failed_without_deleting_projection(monkeypatch):
    db = _FakeDB()
    cursor = SimpleNamespace(cursor_key='coil_snapshots', cursor_value='cursor-1', last_event_at=None, last_synced_at=None, window_started_at=None)
    db.cursor = cursor

    def fail(**kwargs):
        raise RuntimeError('mes offline')

    monkeypatch.setattr('app.services.mes_sync_service._ensure_cursor', lambda _db, *, cursor_key: cursor)
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: SimpleNamespace(list_coil_snapshots=fail))

    with pytest.raises(RuntimeError, match='mes offline'):
        mes_sync_service.sync_coil_snapshots(db, now=datetime(2026, 5, 2, 8, 35, tzinfo=UTC))

    run_log = next(item for item in db.added if item.__class__.__name__ == 'MesSyncRunLog')
    assert run_log.status == 'failed'
    assert db.deleted == []
