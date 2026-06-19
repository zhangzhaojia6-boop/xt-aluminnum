from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.adapters.mes_adapter import CoilSnapshot, MesMachineLineSource, MesSourceRecord, MesWipTotal
from app.database import Base
from app.models.mes import (
    CoilFlowEvent,
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMaterialRecord,
    MesReferenceItem,
    MesStockRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
    MesYieldRecord,
)
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


class _FakePostgresBind:
    dialect = SimpleNamespace(name='postgresql')


class _FakePostgresDB(_FakeDB):
    def __init__(self):
        super().__init__()
        self.executed = []

    def get_bind(self):
        return _FakePostgresBind()

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))


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
    monkeypatch.setattr('app.services.mes_sync_service._upsert_snapshot', lambda _db, *, snapshot, synced_at, **_kwargs: (True, False))
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


def test_upsert_snapshot_uses_top_level_sqlserver_id_and_upgrades_legacy_fallback(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-coil-upgrade.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, CoilFlowEvent.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    synced_at = datetime(2026, 6, 1, 8, 35, tzinfo=UTC)

    with Session() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='fallback:26RA04734:R2-7283-1',
                tracking_card_no='R2-7283-1',
                mes_product_id='997a7b88-50da-4495-a654-da1c0c827dbc',
                current_process='剪切',
            )
        )
        db.commit()

        changed, replayed = mes_sync_service._upsert_snapshot(
            db,
            snapshot=CoilSnapshot(
                coil_id='MES:997a7b88-50da-4495-a654-da1c0c827dbc',
                tracking_card_no='R2-7283-1',
                batch_no='26RA04734',
                process_code='包装',
                metadata={
                    'Id': '997a7b88-50da-4495-a654-da1c0c827dbc',
                    'MaterialCode': 'R2-7283-1',
                    'CurrentProcess': '包装',
                },
            ),
            synced_at=synced_at,
        )
        db.commit()

        rows = db.scalars(select(MesCoilSnapshot)).all()

    assert changed is True
    assert replayed is False
    assert len(rows) == 1
    assert rows[0].coil_id == 'MES:997a7b88-50da-4495-a654-da1c0c827dbc'
    assert rows[0].mes_product_id == '997a7b88-50da-4495-a654-da1c0c827dbc'
    assert rows[0].current_process == '包装'


def test_upsert_snapshot_maps_real_xtal_product_aliases():
    db = _FakeDB()
    snapshot = CoilSnapshot(
        coil_id='MES:product-real',
        tracking_card_no='MC-REAL',
        batch_no='BN-REAL',
        contract_no='HT-REAL',
        status='1',
        metadata={
            'Id': 'product-real',
            'MaterialCode': 'MC-REAL',
            'Customer': '客户A',
            'Alloy': '3003',
            'State': 'H24',
            'Specification': '0.72*1220*C',
            'Weight': '6350',
            'InStockNetWeight': '6200',
            'Status': 1,
            'CardStatus': 2,
            'PrintStatus': 3,
        },
    )

    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 6, 1, 8, 35, tzinfo=UTC))

    entity = next(item for item in db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert entity.contract_no == 'HT-REAL'
    assert entity.customer_alias == '客户A'
    assert entity.material_weight == 6350.0
    assert entity.net_weight == 6200.0
    assert entity.status_name == '1'
    assert entity.card_status_name == '2'
    assert entity.production_status == '3'


def test_upsert_snapshot_business_date_uses_event_time_production_day_boundary():
    db = _FakeDB()
    snapshot = CoilSnapshot(
        coil_id='coil-boundary',
        tracking_card_no='BN-BOUNDARY',
        status='running',
        event_time=datetime(2026, 6, 1, 15, 30, tzinfo=UTC),
        metadata={'Product': {'Id': 'boundary'}, 'CurrentWorkShop': '冷轧', 'CurrentProcess': '轧制'},
    )

    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 6, 1, 15, 31, tzinfo=UTC))

    entity = next(item for item in db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert entity.business_date == date(2026, 6, 1)
    assert entity.source_payload['business_date'] == '2026-06-01'


def test_upsert_snapshot_business_date_prefers_event_time_over_updated_at():
    db = _FakeDB()
    snapshot = CoilSnapshot(
        coil_id='coil-event-priority',
        tracking_card_no='BN-EVENT',
        status='running',
        event_time=datetime(2026, 6, 1, 15, 29, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 1, 0, tzinfo=UTC),
        metadata={'Product': {'Id': 'event-priority'}, 'CurrentWorkShop': '冷轧', 'CurrentProcess': '轧制'},
    )

    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 6, 2, 1, 1, tzinfo=UTC))

    entity = next(item for item in db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert entity.business_date == date(2026, 6, 1)
    assert entity.updated_from_mes_at == datetime(2026, 6, 2, 1, 0, tzinfo=UTC)


def test_upsert_snapshot_business_date_switches_at_0750_shanghai_time():
    before_boundary_db = _FakeDB()
    before_boundary = CoilSnapshot(
        coil_id='coil-before-boundary',
        tracking_card_no='BN-BEFORE-BOUNDARY',
        status='running',
        event_time=datetime(2026, 6, 1, 23, 49, tzinfo=UTC),
        metadata={'Product': {'Id': 'before-boundary'}, 'CurrentWorkShop': '冷轧', 'CurrentProcess': '轧制'},
    )

    mes_sync_service._upsert_snapshot(
        before_boundary_db,
        snapshot=before_boundary,
        synced_at=datetime(2026, 6, 1, 23, 51, tzinfo=UTC),
    )

    before_entity = next(item for item in before_boundary_db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert before_entity.business_date == date(2026, 6, 1)

    at_boundary_db = _FakeDB()
    at_boundary = CoilSnapshot(
        coil_id='coil-at-boundary',
        tracking_card_no='BN-AT-BOUNDARY',
        status='running',
        event_time=datetime(2026, 6, 1, 23, 50, tzinfo=UTC),
        metadata={'Product': {'Id': 'at-boundary'}, 'CurrentWorkShop': '冷轧', 'CurrentProcess': '轧制'},
    )

    mes_sync_service._upsert_snapshot(
        at_boundary_db,
        snapshot=at_boundary,
        synced_at=datetime(2026, 6, 1, 23, 51, tzinfo=UTC),
    )

    at_entity = next(item for item in at_boundary_db.added if item.__class__.__name__ == 'MesCoilSnapshot')
    assert at_entity.business_date == date(2026, 6, 2)


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


def test_upsert_snapshot_locks_projected_key_on_postgresql():
    db = _FakePostgresDB()
    snapshot = CoilSnapshot(
        coil_id='',
        tracking_card_no='BN-2602',
        batch_no='BN-2602',
        metadata={'MaterialCode': '5052-O'},
    )

    mes_sync_service._upsert_snapshot(db, snapshot=snapshot, synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC))

    assert db.executed == [
        (
            'SELECT pg_advisory_xact_lock(hashtext(:lock_key))',
            {'lock_key': 'mes_coil_snapshot:fallback:BN-2602:5052-O'},
        )
    ]


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


def test_sync_coil_list_deduplicates_projected_ids_before_commit(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-sync-dedup.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, CoilFlowEvent.__table__, MesDailyWipSnapshot.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    snapshot = CoilSnapshot(
        coil_id='vendor-row',
        tracking_card_no='26RA03629',
        batch_no='26RA03629',
        process_code='冷轧',
        status='生产中',
        metadata={
            'MaterialCode': '26-s-3-065-1',
            'CurrentWorkShop': '2050车间',
            'CurrentProcess': '冷轧',
        },
        updated_at=datetime(2026, 5, 6, 8, 16, tzinfo=UTC),
    )

    with Session() as db:
        stats_one = mes_sync_service._sync_coil_list(
            db,
            cursor_key='mes_follow_cards',
            rows=[snapshot, snapshot],
            synced_at=datetime(2026, 5, 6, 8, 17, tzinfo=UTC),
        )
        stats_two = mes_sync_service._sync_coil_list(
            db,
            cursor_key='mes_dispatch',
            rows=[snapshot],
            synced_at=datetime(2026, 5, 6, 8, 18, tzinfo=UTC),
        )
        db.commit()

        row_count = db.scalar(select(func.count()).select_from(MesCoilSnapshot))
        entity = db.scalar(select(MesCoilSnapshot))

    assert stats_one.fetched_count == 2
    assert stats_one.upserted_count == 1
    assert stats_two.fetched_count == 1
    assert row_count == 1
    assert entity.coil_id == 'fallback:26RA03629:26-s-3-065-1'


def test_refresh_daily_wip_snapshots_groups_current_coils_by_business_date(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-daily-wip-refresh.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesDailyWipSnapshot.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    with Session() as db:
        db.add_all([
            MesCoilSnapshot(
                coil_id='MES:WIP-1',
                tracking_card_no='WIP-1',
                business_date=date(2026, 6, 1),
                current_workshop='冷轧车间',
                current_process='轧制',
                material_weight=2500,
                feeding_weight=7.5,
            ),
            MesCoilSnapshot(
                coil_id='MES:WIP-2',
                tracking_card_no='WIP-2',
                business_date=date(2026, 6, 1),
                current_workshop='冷轧车间',
                current_process='轧制',
                material_weight=3500,
                feeding_weight=8.5,
            ),
            MesCoilSnapshot(
                coil_id='MES:OLD-WIP',
                tracking_card_no='OLD-WIP',
                business_date=date(2026, 5, 31),
                current_workshop='冷轧车间',
                current_process='轧制',
                material_weight=99000,
                feeding_weight=99,
            ),
            MesCoilSnapshot(
                coil_id='MES:STOCK',
                tracking_card_no='STOCK',
                business_date=date(2026, 6, 1),
                current_workshop='冷轧车间',
                current_process='入库',
                status_name='已入库',
                material_weight=9000,
                feeding_weight=9,
            ),
        ])
        db.commit()

        count = mes_sync_service.refresh_daily_wip_snapshots_from_coils(
            db,
            business_date=date(2026, 6, 1),
            snapshot_at=datetime(2026, 6, 1, 15, 30, tzinfo=UTC),
        )
        db.commit()
        rows = db.scalars(select(MesDailyWipSnapshot)).all()

    assert count == 1
    assert len(rows) == 1
    assert rows[0].business_date == date(2026, 6, 1)
    assert rows[0].workshop_name == '冷轧车间'
    assert rows[0].process_name == '轧制'
    assert rows[0].coil_count == 2
    assert float(rows[0].material_weight_tons) == 6.0
    assert float(rows[0].feeding_weight_tons) == 16.0


def test_mes_snapshot_business_date_uses_production_0750_anchor() -> None:
    before_anchor = CoilSnapshot(
        coil_id='MES:BEFORE',
        tracking_card_no='BEFORE',
        event_time=datetime(2026, 6, 1, 23, 49, tzinfo=UTC),
    )
    at_anchor = CoilSnapshot(
        coil_id='MES:ANCHOR',
        tracking_card_no='ANCHOR',
        event_time=datetime(2026, 6, 1, 23, 50, tzinfo=UTC),
    )
    from_updated_at = CoilSnapshot(
        coil_id='MES:UPDATED',
        tracking_card_no='UPDATED',
        updated_at=datetime(2026, 6, 2, 0, 10, tzinfo=UTC),
    )

    assert mes_sync_service._snapshot_business_date(before_anchor) == date(2026, 6, 1)
    assert mes_sync_service._snapshot_business_date(at_anchor) == date(2026, 6, 2)
    assert mes_sync_service._snapshot_business_date(from_updated_at) == date(2026, 6, 2)


def test_sync_coil_list_refreshes_previous_daily_wip_date_when_coil_moves(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-daily-wip-move.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, CoilFlowEvent.__table__, MesDailyWipSnapshot.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    with Session() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES:move-1',
                tracking_card_no='MOVE-1',
                business_date=date(2026, 5, 31),
                current_workshop='冷轧车间',
                current_process='轧制',
                material_weight=1000,
                feeding_weight=1,
                updated_from_mes_at=datetime(2026, 5, 31, 7, 0, tzinfo=UTC),
            )
        )
        db.add(
            MesDailyWipSnapshot(
                business_date=date(2026, 5, 31),
                workshop_name='冷轧车间',
                process_name='轧制',
                coil_count=1,
                material_weight_tons=1,
                feeding_weight_tons=1,
                source='mes_coil_snapshot',
            )
        )
        db.commit()

        mes_sync_service._sync_coil_list(
            db,
            cursor_key='mes_follow_cards',
            rows=[
                CoilSnapshot(
                    coil_id='vendor-move',
                    tracking_card_no='MOVE-1',
                    status='生产中',
                    event_time=datetime(2026, 6, 1, 15, 30, tzinfo=UTC),
                    updated_at=datetime(2026, 6, 1, 15, 31, tzinfo=UTC),
                    metadata={
                        'Product': {'Id': 'move-1'},
                        'CurrentWorkShop': '冷轧车间',
                        'CurrentProcess': '轧制',
                        'MaterialWeight': '2500',
                        'FeedingWeight': '3',
                    },
                )
            ],
            synced_at=datetime(2026, 6, 1, 15, 32, tzinfo=UTC),
        )
        db.commit()

        old_rows = db.scalars(
            select(MesDailyWipSnapshot).where(MesDailyWipSnapshot.business_date == date(2026, 5, 31))
        ).all()
        new_row = db.scalar(
            select(MesDailyWipSnapshot).where(MesDailyWipSnapshot.business_date == date(2026, 6, 1))
        )

    assert old_rows == []
    assert new_row is not None
    assert new_row.coil_count == 1
    assert float(new_row.material_weight_tons) == 2.5
    assert float(new_row.feeding_weight_tons) == 3.0


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


def test_sync_coil_snapshots_retries_transient_adapter_failures(monkeypatch):
    db = _FakeDB()
    cursor = SimpleNamespace(cursor_key='coil_snapshots', cursor_value='cursor-1', last_event_at=None, last_synced_at=None, window_started_at=None)
    db.cursor = cursor
    snapshot = CoilSnapshot(
        coil_id='coil-retry',
        tracking_card_no='RA260099',
        updated_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC),
    )
    calls = {'count': 0}

    def flaky(**kwargs):
        calls['count'] += 1
        if calls['count'] == 1:
            raise RuntimeError('temporary MES timeout')
        return [snapshot], 'cursor-2'

    monkeypatch.setattr('app.services.mes_sync_service._ensure_cursor', lambda _db, *, cursor_key: cursor)
    monkeypatch.setattr('app.services.mes_sync_service._upsert_snapshot', lambda _db, *, snapshot, synced_at, **_kwargs: (True, False))
    monkeypatch.setattr('app.services.mes_sync_service._sleep_before_retry', lambda _seconds: None)
    monkeypatch.setattr('app.services.mes_sync_service.settings.MES_SYNC_RETRY_LIMIT', 1)
    monkeypatch.setattr('app.services.mes_sync_service.settings.MES_SYNC_BACKOFF_SECONDS', 0)
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: SimpleNamespace(list_coil_snapshots=flaky))

    payload = mes_sync_service.sync_coil_snapshots(db, now=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))

    run_log = next(item for item in db.added if item.__class__.__name__ == 'MesSyncRunLog')
    assert payload.status == 'success'
    assert payload.fetched_count == 1
    assert calls['count'] == 2
    assert run_log.status == 'success'
    assert run_log.metadata_json['attempt_count'] == 2


def test_sync_coil_snapshots_does_not_mark_internal_write_error_as_vendor_failure(monkeypatch):
    db = _FakeDB()
    cursor = SimpleNamespace(cursor_key='coil_snapshots', cursor_value='cursor-1', last_event_at=None, last_synced_at=None, window_started_at=None)
    db.cursor = cursor
    snapshot = CoilSnapshot(
        coil_id='coil-write-error',
        tracking_card_no='RA260100',
        updated_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC),
    )

    def write_failure(*_args, **_kwargs):
        raise RuntimeError('local upsert failed')

    monkeypatch.setattr('app.services.mes_sync_service._ensure_cursor', lambda _db, *, cursor_key: cursor)
    monkeypatch.setattr('app.services.mes_sync_service._upsert_snapshot', write_failure)
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: SimpleNamespace(list_coil_snapshots=lambda **_kwargs: ([snapshot], 'cursor-2')))

    with pytest.raises(RuntimeError, match='local upsert failed'):
        mes_sync_service.sync_coil_snapshots(db, now=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))

    run_log = next(item for item in db.added if item.__class__.__name__ == 'MesSyncRunLog')
    assert run_log.status == 'running'


def test_sync_mes_projection_keeps_successful_sources_when_one_source_fails(monkeypatch):
    db = _FakeDB()
    snapshot = CoilSnapshot(
        coil_id='vendor-row-1',
        tracking_card_no='BN-2601',
        batch_no='BN-2601',
        metadata={'Product': {'Id': 8842}, 'CurrentWorkShop': '冷轧', 'CurrentProcess': '轧制'},
        updated_at=datetime(2026, 5, 2, 8, 30, tzinfo=UTC),
    )

    class Adapter:
        def list_crafts(self):
            return []

        def list_devices(self):
            return []

        def list_follow_cards(self, *, limit):
            return []

        def list_dispatch(self, *, limit):
            return [snapshot]

        def list_wip_totals(self):
            raise RuntimeError('MES MVC request failed after relogin: /Dispatch/DoingReportTotal')

        def list_stock(self, *, limit):
            return []

        def list_machine_line_sources(self):
            return []

    monkeypatch.setattr('app.services.mes_sync_service._configured_mvc_wip_adapter', lambda: None)
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: Adapter())

    stats = mes_sync_service.sync_mes_projection(db, now=datetime(2026, 5, 2, 8, 35, tzinfo=UTC))

    by_key = {item.cursor_key: item for item in stats}
    assert by_key['mes_dispatch'].status == 'success'
    assert by_key['mes_dispatch'].upserted_count == 1
    assert by_key['mes_wip_total'].status == 'failed'
    assert by_key['mes_wip_total'].error_message == 'MES MVC request failed after relogin: /Dispatch/DoingReportTotal'
    assert next(item for item in db.added if item.__class__.__name__ == 'MesCoilSnapshot').coil_id == 'MES:8842'


def test_mes_projection_profiles_split_realtime_business_and_reference(monkeypatch):
    def stat(key: str) -> mes_sync_service.MesSyncStats:
        return mes_sync_service.MesSyncStats(
            cursor_key=key,
            fetched_count=0,
            upserted_count=0,
            replayed_count=0,
            next_cursor=None,
            lag_seconds=None,
            last_event_at=None,
            last_synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC),
            status='success',
        )

    patched = {
        'sync_mes_follow_cards': 'mes_follow_cards',
        'sync_mes_dispatch': 'mes_dispatch',
        'sync_mes_wip_total': 'mes_wip_total',
        'sync_mes_stock': 'mes_stock',
        'sync_mes_workshop_process_records': 'mes_workshop_process_records',
        'sync_mes_stock_records': 'mes_stock_records',
        'sync_mes_material_records': 'mes_material_records',
        'sync_mes_yield_records': 'mes_yield_records',
        'sync_mes_crafts': 'mes_crafts',
        'sync_mes_devices': 'mes_devices',
        'sync_mes_reference_items': 'mes_reference_items',
        'sync_mes_machine_lines': 'mes_machine_lines',
        'sync_mes_finished_inbound_records_between': 'mes_finished_inbound_records_between',
        'sync_mes_delivery_records_between': 'mes_delivery_records_between',
    }
    for func_name, cursor_key in patched.items():
        if func_name in {'sync_mes_finished_inbound_records_between', 'sync_mes_delivery_records_between'}:
            monkeypatch.setattr(
                mes_sync_service,
                func_name,
                lambda _db, cursor_key=cursor_key, **_kwargs: stat(cursor_key),
            )
            continue
        monkeypatch.setattr(
            mes_sync_service,
            func_name,
            lambda _db, now=None, cursor_key=cursor_key: stat(cursor_key),
        )

    db = _FakeDB()
    realtime = mes_sync_service.sync_mes_realtime_projection(db)
    business = mes_sync_service.sync_mes_business_projection(db)
    reference = mes_sync_service.sync_mes_reference_projection(db)

    assert [item.cursor_key for item in realtime] == ['mes_follow_cards', 'mes_dispatch']
    assert [item.cursor_key for item in business] == [
        'mes_wip_total',
        'mes_stock',
        'mes_workshop_process_records',
        'mes_stock_records',
        'mes_material_records',
        'mes_yield_records',
        'mes_finished_inbound_records_between',
        'mes_delivery_records_between',
    ]
    assert [item.cursor_key for item in reference] == [
        'mes_crafts',
        'mes_devices',
        'mes_reference_items',
        'mes_machine_lines',
    ]


def test_sync_projection_step_reraises_database_errors():
    db = _FakeDB()

    def broken_runner(_db, *, now):
        _ = now
        raise OperationalError('SELECT mes_coil_snapshots', {}, Exception('database unavailable'))

    with pytest.raises(OperationalError):
        mes_sync_service._sync_projection_step(
            db,
            cursor_key='mes_dispatch',
            synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC),
            runner=broken_runner,
        )


def test_sync_projection_step_marks_not_implemented_as_skipped():
    db = _FakeDB()

    def unsupported_runner(_db, *, now):
        _ = now
        raise NotImplementedError('not implemented for this adapter')

    stats = mes_sync_service._sync_projection_step(
        db,
        cursor_key='mes_reference_items',
        synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC),
        runner=unsupported_runner,
    )

    assert stats.status == 'skipped'
    assert stats.fetched_count == 0
    assert stats.upserted_count == 0
    assert stats.error_message == 'not implemented: not implemented for this adapter'


def test_sync_projection_step_retries_transient_adapter_failures(monkeypatch):
    db = _FakeDB()
    calls = {'count': 0}

    def flaky_runner(_db, *, now):
        calls['count'] += 1
        if calls['count'] == 1:
            raise RuntimeError('temporary projection timeout')
        return mes_sync_service.MesSyncStats(
            cursor_key='mes_dispatch',
            fetched_count=1,
            upserted_count=1,
            replayed_count=0,
            next_cursor=None,
            lag_seconds=0,
            last_event_at=now,
            last_synced_at=now,
            status='success',
        )

    monkeypatch.setattr('app.services.mes_sync_service._sleep_before_retry', lambda _seconds: None)
    monkeypatch.setattr('app.services.mes_sync_service.settings.MES_SYNC_RETRY_LIMIT', 1)
    monkeypatch.setattr('app.services.mes_sync_service.settings.MES_SYNC_BACKOFF_SECONDS', 0)

    stats = mes_sync_service._sync_projection_step(
        db,
        cursor_key='mes_dispatch',
        synced_at=datetime(2026, 5, 2, 8, 35, tzinfo=UTC),
        runner=flaky_runner,
    )

    assert stats.status == 'success'
    assert stats.upserted_count == 1
    assert calls['count'] == 2


def test_sync_mes_extended_sources_persists_business_tables_and_strips_sensitive_payloads(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-extended-sync.db'}", future=True)
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
    synced_at = datetime(2026, 6, 1, 8, 35, tzinfo=UTC)

    class Adapter:
        def list_workshop_process_records(self, *, limit):
            return [
                MesSourceRecord(
                    source_id='101',
                    source_path='/Report/ProductionWorkshopReport',
                    event_time=datetime(2026, 6, 1, 15, 15, tzinfo=UTC),
                    metadata={
                        'Id': 101,
                        'PBatchNumber': '26RA04597',
                        'CustomerSimple': '河南富邦鑫泰',
                        'WorkShop': '园区在线车间',
                        'Process': '在线退火',
                        'Worker': '刘统帅',
                        'DeviceName': '园区北线（WIFI）',
                        'BeginWeight': '7550',
                        'EndWeight': '7450',
                        'YieldRate': '98.7',
                        'Password': 'secret',
                    },
                )
            ]

        def list_stock_records(self, *, limit):
            return [
                MesSourceRecord(
                    source_id='stock-1',
                    source_path='/Stock/GetList',
                    event_time=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
                    metadata={
                        'Id': 'stock-1',
                        'BatchNumber': '26RA04597',
                        'CustomerSimple': '河南富邦鑫泰',
                        'ContractCode': 'HT-2601',
                        'NetWeight': '11800',
                        'GrossWeight': '12000',
                        'InStockDate': '2026-06-01 16:00:00',
                        'StatusName': '已入库',
                    },
                )
            ]

        def list_material_records(self, *, limit):
            return [
                MesSourceRecord(
                    source_id='26-s-2-085-2',
                    source_path='/Material/GetList',
                    event_time=datetime(2026, 6, 1, 11, 10, tzinfo=UTC),
                    metadata={
                        'MaterialCode': '26-s-2-085-2',
                        'WorkShopRolling': '铸三车间',
                        'WorkShopLine': '2#',
                        'PositionName': 'D区',
                        'Alloy': '3004',
                        'Specification': '3.9*1110*C',
                        'Weight': '10338',
                        'StatusName': '可使用',
                    },
                )
            ]

        def list_yield_records(self, *, limit):
            return [
                MesSourceRecord(
                    source_id='yield-1',
                    source_path='/Report/YieldReport',
                    event_time=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
                    metadata={
                        'Id': 'yield-1',
                        'BatchNumber': '26RA04597',
                        'ContractCode': 'HT-2601',
                        'CustomerSimple': '河南富邦鑫泰',
                        'ContractTotalWeight': '42.5',
                        'FeedingWeight': '12.4',
                        'InStockNetWeight': '11.8',
                        'YieldRate': '95.16',
                    },
                )
            ]

        def list_reference_items(self):
            return [
                MesSourceRecord(
                    source_id='device-1',
                    source_path='/Device/GetList',
                    metadata={
                        'Id': 'device-1',
                        'Name': '园区北线（WIFI）',
                        'WorkShop': '园区在线车间',
                        'Craft': '在线退火',
                        'StatusName': '正常',
                        'Password': 'must-not-persist',
                    },
                )
            ]

        def list_wip_totals(self):
            return [
                MesWipTotal(
                    workshop_name='2050车间',
                    doing_weight=430.0,
                    metadata={'process_totals': {'冷轧': 430.0}},
                )
            ]

    monkeypatch.setattr('app.services.mes_sync_service._configured_mvc_wip_adapter', lambda: None)
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: Adapter())

    with Session() as db:
        process_stats = mes_sync_service.sync_mes_workshop_process_records(db, now=synced_at)
        stock_stats = mes_sync_service.sync_mes_stock_records(db, now=synced_at)
        material_stats = mes_sync_service.sync_mes_material_records(db, now=synced_at)
        yield_stats = mes_sync_service.sync_mes_yield_records(db, now=synced_at)
        reference_stats = mes_sync_service.sync_mes_reference_items(db, now=synced_at)
        wip_stats = mes_sync_service.sync_mes_wip_total(db, now=synced_at)
        db.commit()

        process = db.scalar(select(MesWorkshopProcessRecord))
        stock = db.scalar(select(MesStockRecord))
        material = db.scalar(select(MesMaterialRecord))
        yield_record = db.scalar(select(MesYieldRecord))
        reference = db.scalar(select(MesReferenceItem))
        wip = db.scalar(select(MesWipTotalSnapshot))

    assert process_stats.upserted_count == 1
    assert stock_stats.upserted_count == 1
    assert material_stats.upserted_count == 1
    assert yield_stats.upserted_count == 1
    assert reference_stats.upserted_count == 1
    assert wip_stats.upserted_count == 1
    assert process.batch_no == '26RA04597'
    assert process.customer_alias == '河南富邦鑫泰'
    assert process.output_weight_kg == 7450.0
    assert float(process.output_weight_tons) == 7.45
    assert process.business_date == date(2026, 6, 1)
    assert 'Password' not in process.source_payload
    assert stock.contract_no == 'HT-2601'
    assert float(stock.net_weight_tons) == 11.8
    assert stock.business_date == date(2026, 6, 1)
    assert material.workshop_name == '铸三车间'
    assert float(material.weight_tons) == 10.338
    assert float(yield_record.contract_total_weight_tons) == 42.5
    assert yield_record.business_date == date(2026, 6, 1)
    assert reference.source_type == 'device'
    assert 'Password' not in reference.source_payload
    assert wip.workshop_name == '2050车间'
    assert wip.process_name == '冷轧'
    assert float(wip.doing_weight_tons) == 430.0


def test_stock_record_business_date_prefers_create_date_over_allocation_date():
    record = MesSourceRecord(
        source_id='stock-cross-day',
        source_path='sqlserver:stock_records',
        event_time=datetime(2026, 6, 2, 1, 10, tzinfo=UTC),
        metadata={
            'Id': 'stock-cross-day',
            'BatchNumber': '26RA04967',
            'NetWeight': '6350',
            'AllocationDate': datetime(2026, 6, 1, 16, 20, tzinfo=UTC),
            'CreateDate': datetime(2026, 6, 2, 1, 10, tzinfo=UTC),
        },
    )

    fields = mes_sync_service._stock_fields(record, synced_at=datetime(2026, 6, 2, 1, 15, tzinfo=UTC))

    assert fields['in_stock_date'] == datetime(2026, 6, 2, 1, 10, tzinfo=UTC)
    assert fields['business_date'] == date(2026, 6, 2)


def test_sync_finished_inbound_and_delivery_records_between(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-stock-window-sync.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesStockRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    synced_at = datetime(2026, 6, 18, 1, 0, tzinfo=UTC)
    start_at = datetime(2026, 6, 17, 7, 30)
    end_at = datetime(2026, 6, 18, 7, 30)

    class Adapter:
        def list_finished_inbound_records_between(self, *, start_at, end_at, limit=1000, offset=0):
            _ = (start_at, end_at, limit)
            if offset:
                return []
            return [
                MesSourceRecord(
                    source_id='stock_header_records:inbound-1',
                    source_path='sqlserver:stock_header_records',
                    metadata={
                        'Id': 'inbound-1',
                        'FromDepartment': '园区精整',
                        'ToDepartment': '成品库',
                        'TotalNetWeight': '303031',
                        'InStockDate': datetime(2026, 6, 17, 9, 0),
                    },
                )
            ]

        def list_delivery_records_between(self, *, start_at, end_at, limit=1000, offset=0):
            _ = (start_at, end_at, limit)
            if offset:
                return []
            return [
                MesSourceRecord(
                    source_id='delivery_records:delivery-1',
                    source_path='sqlserver:delivery_records',
                    metadata={
                        'Id': 'delivery-1',
                        'DeliveryCode': 'FH-1',
                        'NetWeight': '222306',
                        'OperateDate': datetime(2026, 6, 17, 14, 0),
                        'CreateDate': datetime(2026, 6, 18, 8, 0),
                    },
                )
            ]

    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: Adapter())

    with Session() as db:
        inbound_stats = mes_sync_service.sync_mes_finished_inbound_records_between(
            db,
            start_at=start_at,
            end_at=end_at,
            now=synced_at,
        )
        delivery_stats = mes_sync_service.sync_mes_delivery_records_between(
            db,
            start_at=start_at,
            end_at=end_at,
            now=synced_at,
        )
        db.commit()
        rows = db.execute(select(MesStockRecord).order_by(MesStockRecord.source_path.asc())).scalars().all()

    assert inbound_stats.fetched_count == 1
    assert delivery_stats.fetched_count == 1
    by_source = {row.source_path: row for row in rows}
    assert float(by_source['sqlserver:stock_header_records'].net_weight_tons) == 303.031
    assert by_source['sqlserver:stock_header_records'].business_date == date(2026, 6, 17)
    assert float(by_source['sqlserver:delivery_records'].net_weight_tons) == 222.306
    assert by_source['sqlserver:delivery_records'].business_date == date(2026, 6, 17)


def test_sync_mes_wip_total_merges_duplicate_source_ids(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-wip-duplicate.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesWipTotalSnapshot.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    synced_at = datetime(2026, 6, 1, 8, 35, tzinfo=UTC)

    class Adapter:
        def list_wip_totals(self):
            return [
                MesWipTotal(
                    workshop_name='1450车间',
                    doing_count=4,
                    doing_weight=26.5,
                    metadata={'ProcessName': '剪切'},
                ),
                MesWipTotal(
                    workshop_name='1450车间',
                    doing_count=2,
                    doing_weight=10.5,
                    metadata={'ProcessName': '包装'},
                ),
            ]

    monkeypatch.setattr('app.services.mes_sync_service._configured_mvc_wip_adapter', lambda: None)
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: Adapter())

    with Session() as db:
        stats = mes_sync_service.sync_mes_wip_total(db, now=synced_at)
        db.commit()
        rows = db.scalars(select(MesWipTotalSnapshot)).all()

    assert stats.fetched_count == 2
    assert stats.upserted_count == 1
    assert len(rows) == 1
    assert rows[0].source_id == '1450车间:total'
    assert rows[0].doing_count == 6
    assert float(rows[0].doing_weight_tons) == 37.0


def test_sync_mes_wip_total_prefers_mvc_page_totals(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-wip-mvc.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesWipTotalSnapshot.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    synced_at = datetime(2026, 6, 19, 8, 35, tzinfo=UTC)

    class MvcAdapter:
        def list_wip_totals(self):
            return [
                MesWipTotal(
                    workshop_name='2050车间',
                    doing_weight=304.5,
                    metadata={'process_totals': {'冷轧': 304.5}},
                )
            ]

    class SqlAdapter:
        def list_wip_totals(self):
            return [
                MesWipTotal(
                    workshop_name='2050车间',
                    doing_weight=9999.0,
                    metadata={'process_totals': {'包装': 9999.0}},
                )
            ]

    monkeypatch.setattr('app.services.mes_sync_service._configured_mvc_wip_adapter', lambda: MvcAdapter())
    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: SqlAdapter())

    with Session() as db:
        stats = mes_sync_service.sync_mes_wip_total(db, now=synced_at)
        db.commit()
        rows = db.scalars(select(MesWipTotalSnapshot)).all()

    assert stats.fetched_count == 1
    assert len(rows) == 1
    assert rows[0].source_id == '2050车间:冷轧'
    assert float(rows[0].doing_weight_tons) == 304.5


def test_sync_reference_items_falls_back_when_mes_returns_zero_uuid_ids(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-reference-zero-ids.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesReferenceItem.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    zero_uuid = '00000000-0000-0000-0000-000000000000'
    synced_at = datetime(2026, 6, 1, 8, 35, tzinfo=UTC)

    class Adapter:
        def list_reference_items(self):
            return [
                MesSourceRecord(
                    source_id=zero_uuid,
                    source_path='/Material/GetBoardList',
                    metadata={'Id': zero_uuid, 'Name': '7#', 'PID': zero_uuid},
                ),
                MesSourceRecord(
                    source_id=zero_uuid,
                    source_path='/Material/GetBoardList',
                    metadata={'Id': zero_uuid, 'Name': '8#', 'PID': zero_uuid},
                ),
            ]

    monkeypatch.setattr('app.services.mes_sync_service.get_mes_adapter', lambda: Adapter())

    with Session() as db:
        stats = mes_sync_service.sync_mes_reference_items(db, now=synced_at)
        db.commit()
        rows = db.scalars(select(MesReferenceItem).order_by(MesReferenceItem.source_id)).all()

    assert stats.fetched_count == 2
    assert stats.upserted_count == 2
    assert [row.source_id for row in rows] == ['7#', '8#']
