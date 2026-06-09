from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.master import Equipment, MasterCodeAlias, Team, Workshop
from app.models.mes import (
    CoilFlowEvent,
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMachineLineSnapshot,
    MesStockRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
    MesYieldRecord,
)
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import factory_command_service, realtime_service


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(
        self,
        *,
        coils=None,
        lines=None,
        events=None,
        workshops=None,
        shift_rows=None,
        mobile_reports=None,
        equipment=None,
        process_records=None,
        stock_records=None,
        yield_records=None,
        wip_snapshots=None,
        daily_wip_snapshots=None,
    ):
        self.coils = coils or []
        self.lines = lines or []
        self.events = events or []
        self.workshops = workshops or []
        self.shift_rows = shift_rows or []
        self.mobile_reports = mobile_reports or []
        self.equipment = equipment or []
        self.process_records = process_records or []
        self.stock_records = stock_records or []
        self.yield_records = yield_records or []
        self.wip_snapshots = wip_snapshots or []
        self.daily_wip_snapshots = daily_wip_snapshots or []

    def query(self, model):
        if model is MesCoilSnapshot:
            return _Query(self.coils)
        if model is MesMachineLineSnapshot:
            return _Query(self.lines)
        if model is CoilFlowEvent:
            return _Query(self.events)
        if model is Workshop:
            return _Query(self.workshops)
        if model is ShiftProductionData:
            return _Query(self.shift_rows)
        if model is MobileShiftReport:
            return _Query(self.mobile_reports)
        if model is Equipment:
            return _Query(self.equipment)
        if model is MesWorkshopProcessRecord:
            return _Query(self.process_records)
        if model is MesStockRecord:
            return _Query(self.stock_records)
        if model is MesYieldRecord:
            return _Query(self.yield_records)
        if model is MesWipTotalSnapshot:
            return _Query(self.wip_snapshots)
        if model is MesDailyWipSnapshot:
            return _Query(self.daily_wip_snapshots)
        if model is MasterCodeAlias.alias_code:
            return _Query([])
        raise AssertionError(model)


def _coil(**overrides):
    payload = {
        'coil_id': 'MES:1',
        'tracking_card_no': 'BN-1',
        'batch_no': 'BN-1',
        'material_code': '3003-H24',
        'current_workshop': '冷轧',
        'current_process': '轧制',
        'next_workshop': '退火',
        'next_process': '退火',
        'status_name': '生产中',
        'delay_hours': 0.0,
        'net_weight': 10.0,
        'gross_weight': 10.2,
        'feeding_weight': 10.5,
        'process_route_text': '铸轧-冷轧-退火',
        'in_stock_date': None,
        'delivery_date': None,
        'allocation_date': None,
        'last_seen_from_mes_at': datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        'source_payload': {'safe': True},
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _shift_data(**overrides):
    payload = {
        'id': 1,
        'business_date': datetime(2026, 5, 2, 8, 0, tzinfo=UTC).date(),
        'shift_config_id': 1,
        'workshop_id': 1,
        'team_id': None,
        'equipment_id': 101,
        'input_weight': 12.0,
        'output_weight': 10.0,
        'qualified_weight': 9.8,
        'scrap_weight': 0.2,
        'data_status': 'confirmed',
        'updated_at': datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _sqlalchemy_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'factory-command-service.db'}", future=True)
    for table in (MesCoilSnapshot.__table__, MesMachineLineSnapshot.__table__, CoilFlowEvent.__table__):
        table.create(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _factory_realtime_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'factory-command-realtime.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            Equipment.__table__,
            MasterCodeAlias.__table__,
            ShiftConfig.__table__,
            ShiftProductionData.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            DailyConsumableLog.__table__,
            MobileShiftReport.__table__,
            MesCoilSnapshot.__table__,
            MesMachineLineSnapshot.__table__,
            MesWorkshopProcessRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def test_factory_overview_groups_projection_rows_and_labels_estimates(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', net_weight=10.0, delay_hours=0),
            _coil(coil_id='MES:2', current_workshop='退火', current_process=None, net_weight=5.0, delay_hours=4),
            _coil(coil_id='MES:3', current_workshop='成品库', status_name='已入库', net_weight=2.0, in_stock_date=datetime(2026, 5, 2, 9, 0, tzinfo=UTC)),
        ]
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {'lag_seconds': 90, 'last_synced_at': '2026-05-02T08:00:00+00:00', 'last_run_status': 'success'},
    )

    overview = factory_command_service.build_overview(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert overview['freshness']['status'] == 'fresh'
    assert overview['wip_tons'] == 15.0
    assert overview['today_output_tons'] == 2.0
    assert overview['stock_tons'] == 2.0
    assert overview['abnormal_count'] == 1
    assert overview['cost_estimate']['label'] == '经营估算'
    assert 'profit' not in ''.join(overview['cost_estimate'].keys()).lower()
    assert overview['missing_data'] == ['cost_inputs']


def test_factory_overview_falls_back_to_local_shift_data_when_projection_empty(monkeypatch):
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        equipment=[SimpleNamespace(id=101, code='CRM-01', name='1#轧机', workshop_id=1)],
        shift_rows=[
            _shift_data(input_weight=12.0, output_weight=10.0, qualified_weight=9.8),
            _shift_data(id=2, equipment_id=102, input_weight=8.0, output_weight=7.5, qualified_weight=7.2, data_status='submitted'),
            _shift_data(id=3, input_weight=99.0, output_weight=88.0, data_status='pending'),
            _shift_data(id=4, business_date=datetime(2026, 5, 1, tzinfo=UTC).date(), input_weight=20.0, output_weight=18.0),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'unconfigured',
            'configured': False,
            'migration_ready': True,
            'source': 'local_entry',
            'lag_seconds': None,
            'action_required': 'configure_mes',
        },
    )

    overview = factory_command_service.build_overview(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert overview['source'] == 'local_shift_data'
    assert overview['freshness']['source'] == 'local_shift_data'
    assert overview['total_input_tons'] == 20.0
    assert overview['total_output_tons'] == 17.5
    assert overview['today_output_tons'] == 17.5
    assert overview['yield_rate'] == 87.5
    assert overview['workshop_summary'] == [
        {
            'workshop_id': 1,
            'workshop_name': '冷轧',
            'row_count': 2,
            'total_input_tons': 20.0,
            'total_output_tons': 17.5,
            'yield_rate': 87.5,
        }
    ]


def test_factory_overview_respects_explicit_target_date_when_local_latest_is_older(monkeypatch):
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        shift_rows=[
            _shift_data(business_date=date(2026, 5, 1), input_weight=12.0, output_weight=10.0),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'unconfigured',
            'configured': False,
            'migration_ready': True,
            'source': 'local_entry',
            'lag_seconds': None,
            'action_required': 'configure_mes',
        },
    )

    overview = factory_command_service.build_overview(db, now=date(2026, 5, 2))

    assert overview['business_date'] == '2026-05-02'
    assert overview['total_output_tons'] == 0.0
    assert overview['previous_day']['business_date'] == '2026-05-01'
    assert overview['previous_day']['total_output_tons'] == 10.0


def test_factory_overview_includes_pending_mobile_coil_aggregates(monkeypatch):
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        equipment=[SimpleNamespace(id=101, code='CRM-01', name='1#轧机', workshop_id=1)],
        shift_rows=[
            _shift_data(input_weight=12.0, output_weight=10.0, qualified_weight=9.8),
            _shift_data(id=2, input_weight=99.0, output_weight=88.0, data_status='pending', data_source='import'),
            _shift_data(
                id=3,
                input_weight=4000.0,
                output_weight=3500.0,
                qualified_weight=3500.0,
                data_status='pending',
                data_source='mobile_coil_agg',
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'unconfigured',
            'configured': False,
            'migration_ready': True,
            'source': 'local_entry',
            'lag_seconds': None,
            'action_required': 'configure_mes',
        },
    )

    overview = factory_command_service.build_overview(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert overview['source'] == 'local_shift_data'
    assert overview['total_input_tons'] == 16.0
    assert overview['total_output_tons'] == 13.5
    assert overview['workshop_summary'][0]['row_count'] == 2


def test_factory_overview_blends_local_mobile_coil_aggregates_when_projection_exists(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', net_weight=10.0),
        ],
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        equipment=[SimpleNamespace(id=101, code='CRM-01', name='1#轧机', workshop_id=1)],
        shift_rows=[
            _shift_data(
                input_weight=4000.0,
                output_weight=3500.0,
                qualified_weight=3500.0,
                data_status='pending',
                data_source='mobile_coil_agg',
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T08:00:00+00:00',
        },
    )

    overview = factory_command_service.build_overview(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert overview['source'] == 'mixed'
    assert overview['freshness']['source'] == 'mixed'
    assert overview['total_input_tons'] == 4.0
    assert overview['total_output_tons'] == 3.5
    assert overview['today_output_tons'] == 3.5
    assert overview['workshop_summary'] == [
        {
            'workshop_id': 1,
            'workshop_name': '冷轧',
            'row_count': 1,
            'total_input_tons': 4.0,
            'total_output_tons': 3.5,
            'yield_rate': 87.5,
        }
    ]


def test_factory_overview_uses_mes_extended_tables_when_local_rows_absent(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='在线退火分厂', net_weight=10.0),
        ],
        process_records=[
            SimpleNamespace(
                id=1,
                business_date=date(2026, 5, 2),
                workshop_name='在线退火分厂',
                input_weight_tons=12.0,
                output_weight_tons=11.4,
                last_seen_from_mes_at=datetime(2026, 5, 2, 23, 40, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=2,
                business_date=date(2026, 5, 2),
                workshop_name='冷轧',
                input_weight_tons=8.0,
                output_weight_tons=7.1,
                last_seen_from_mes_at=datetime(2026, 5, 2, 22, 10, tzinfo=UTC),
            ),
        ],
        stock_records=[
            SimpleNamespace(
                id=1,
                business_date=date(2026, 5, 2),
                net_weight_tons=6.2,
                last_seen_from_mes_at=datetime(2026, 5, 2, 23, 50, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=2,
                business_date=date(2026, 5, 1),
                net_weight_tons=2.3,
                last_seen_from_mes_at=datetime(2026, 5, 1, 23, 50, tzinfo=UTC),
            ),
        ],
        wip_snapshots=[
            SimpleNamespace(
                id=1,
                workshop_name='在线退火分厂',
                process_name='退火',
                doing_weight_tons=9.5,
                snapshot_at=datetime(2026, 5, 2, 23, 58, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=2,
                workshop_name='冷轧',
                process_name='轧制',
                doing_weight_tons=4.0,
                snapshot_at=datetime(2026, 5, 2, 23, 58, tzinfo=UTC),
            ),
        ],
        yield_records=[
            SimpleNamespace(
                id=1,
                business_date=date(2026, 5, 2),
                yield_rate=93.3,
                last_seen_from_mes_at=datetime(2026, 5, 2, 23, 59, tzinfo=UTC),
            )
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T23:59:00+00:00',
        },
    )

    overview = factory_command_service.build_overview(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert overview['source'] == 'mes_extended'
    assert overview['freshness']['source'] == 'mes_extended'
    assert overview['total_input_tons'] == 20.0
    assert overview['total_output_tons'] == 18.5
    assert overview['yield_rate'] == 92.5
    assert overview['today_output_tons'] == 6.2
    assert overview['stock_tons'] == 8.5
    assert overview['wip_tons'] == 13.5
    assert overview['workshop_summary'] == [
        {
            'workshop_name': '在线退火分厂',
            'row_count': 1,
            'total_input_tons': 12.0,
            'total_output_tons': 11.4,
            'yield_rate': 95.0,
        },
        {
            'workshop_name': '冷轧',
            'row_count': 1,
            'total_input_tons': 8.0,
            'total_output_tons': 7.1,
            'yield_rate': 88.75,
        },
    ]


def test_factory_overview_uses_daily_wip_snapshot_when_only_wip_exists(monkeypatch):
    db = _FakeDB(
        daily_wip_snapshots=[
            SimpleNamespace(
                id=1,
                business_date=date(2026, 5, 2),
                workshop_name='冷轧',
                process_name='轧制',
                coil_count=3,
                material_weight_tons=12.5,
                feeding_weight_tons=18.2,
                snapshot_at=datetime(2026, 5, 2, 23, 58, tzinfo=UTC),
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T23:59:00+00:00',
        },
    )

    overview = factory_command_service.build_overview(db, now=date(2026, 5, 2))
    workshops = factory_command_service.list_workshops(db, now=date(2026, 5, 2))

    assert overview['source'] == 'mes_extended'
    assert overview['wip_tons'] == 12.5
    assert overview['workshop_summary'] == [
        {
            'workshop_name': '冷轧',
            'row_count': 3,
            'total_input_tons': 18.2,
            'total_output_tons': 12.5,
            'yield_rate': None,
        }
    ]
    assert workshops == [
        {
            'workshop_name': '冷轧',
            'active_coil_count': 3,
            'active_tons': 12.5,
            'stalled_count': 0,
            'freshness': {
                'status': 'fresh',
                'lag_seconds': 60,
                'last_synced_at': '2026-05-02T23:59:00+00:00',
                'last_event_at': None,
                'source': 'mes_extended',
                'configured': True,
                'migration_ready': True,
                'action_required': 'none',
                'risk_tone': 'normal',
            },
        }
    ]


def test_factory_workshops_use_mes_extended_process_rows_when_local_rows_absent(monkeypatch):
    db = _FakeDB(
        coils=[],
        process_records=[
            SimpleNamespace(
                id=1,
                business_date=date(2026, 5, 2),
                workshop_name='在线退火分厂',
                output_weight_tons=11.4,
                last_seen_from_mes_at=datetime(2026, 5, 2, 23, 40, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=2,
                business_date=date(2026, 5, 2),
                workshop_name='冷轧',
                output_weight_tons=7.1,
                last_seen_from_mes_at=datetime(2026, 5, 2, 22, 10, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=3,
                business_date=date(2026, 5, 1),
                workshop_name='冷轧',
                output_weight_tons=99.0,
                last_seen_from_mes_at=datetime(2026, 5, 1, 22, 10, tzinfo=UTC),
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T23:59:00+00:00',
        },
    )

    workshops = factory_command_service.list_workshops(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert workshops == [
        {
            'workshop_name': '在线退火分厂',
            'active_coil_count': 1,
            'active_tons': 11.4,
            'stalled_count': 0,
            'freshness': {
                'status': 'fresh',
                'lag_seconds': 60,
                'last_synced_at': '2026-05-02T23:59:00+00:00',
                'last_event_at': None,
                'source': 'mes_extended',
                'configured': True,
                'migration_ready': True,
                'action_required': 'none',
                'risk_tone': 'normal',
            },
        },
        {
            'workshop_name': '冷轧',
            'active_coil_count': 1,
            'active_tons': 7.1,
            'stalled_count': 0,
            'freshness': {
                'status': 'fresh',
                'lag_seconds': 60,
                'last_synced_at': '2026-05-02T23:59:00+00:00',
                'last_event_at': None,
                'source': 'mes_extended',
                'configured': True,
                'migration_ready': True,
                'action_required': 'none',
                'risk_tone': 'normal',
            },
        },
    ]


def test_factory_overview_falls_back_to_local_shift_data_when_fresh_projection_is_empty(monkeypatch):
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        equipment=[SimpleNamespace(id=101, code='CRM-01', name='1#轧机', workshop_id=1)],
        shift_rows=[
            _shift_data(input_weight=11.0, output_weight=9.5, qualified_weight=9.3),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T08:00:00+00:00',
        },
    )

    overview = factory_command_service.build_overview(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert overview['source'] == 'local_shift_data'
    assert overview['freshness']['source'] == 'local_shift_data'
    assert overview['total_input_tons'] == 11.0
    assert overview['total_output_tons'] == 9.5


def test_factory_lists_fall_back_to_local_shift_data_when_projection_empty(monkeypatch):
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        equipment=[
            SimpleNamespace(id=101, code='CRM-01', name='1#轧机', workshop_id=1),
            SimpleNamespace(id=102, code='CRM-02', name='2#轧机', workshop_id=1),
        ],
        shift_rows=[
            _shift_data(equipment_id=101, input_weight=12.0, output_weight=10.0),
            _shift_data(id=2, equipment_id=102, input_weight=8.0, output_weight=7.5, data_status='submitted'),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {'status': 'migration_missing', 'source': 'local_entry', 'lag_seconds': None},
    )

    current_time = datetime(2026, 5, 2, 8, 1, tzinfo=UTC)
    workshops = factory_command_service.list_workshops(db, now=current_time)
    lines = factory_command_service.list_machine_lines(db, now=current_time)
    coils = factory_command_service.list_coils(db)

    assert workshops == [
        {
            'workshop_name': '冷轧',
            'active_coil_count': 2,
            'active_tons': 17.5,
            'stalled_count': 0,
            'freshness': {
                'status': 'migration_missing',
                'lag_seconds': None,
                'last_synced_at': None,
                'last_event_at': None,
                'source': 'local_shift_data',
                'configured': True,
                'migration_ready': True,
                'action_required': 'none',
                'risk_tone': 'normal',
            },
        }
    ]
    assert [item['line_code'] for item in lines] == ['CRM-01', 'CRM-02']
    assert [item['active_tons'] for item in lines] == [10.0, 7.5]
    assert all(item['freshness']['source'] == 'local_shift_data' for item in lines)
    assert coils == []


def test_factory_lists_fall_back_to_unbound_live_machine_lines(monkeypatch):
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        shift_rows=[
            _shift_data(equipment_id=None, shift_config_id=1, input_weight=12000.0, output_weight=10000.0, data_status='pending', data_source='mobile_coil_agg'),
            _shift_data(id=2, equipment_id=None, shift_config_id=3, input_weight=8000.0, output_weight=7500.0, data_status='pending', data_source='mobile_coil_agg'),
            _shift_data(id=3, equipment_id=None, shift_config_id=3, input_weight=4000.0, output_weight=3500.0, data_status='pending', data_source='mobile_coil_agg'),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {'status': 'unconfigured', 'configured': False, 'source': 'local_entry', 'lag_seconds': None},
    )

    lines = factory_command_service.list_machine_lines(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert [item['line_code'] for item in lines] == ['workshop:1:shift:1:unbound', 'workshop:1:shift:3:unbound']
    assert [item['line_name'] for item in lines] == ['未绑定机列 / 1班', '未绑定机列 / 3班']
    assert [item['active_tons'] for item in lines] == [10.0, 11.0]
    assert all(item['machine_binding_status'] == 'unbound' for item in lines)
    assert all(item['freshness']['source'] == 'local_shift_data' for item in lines)


def test_factory_machine_lines_blend_local_mobile_coil_aggregates_when_projection_exists(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', machine_code='CRM-01', net_weight=10.0),
        ],
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        lines=[SimpleNamespace(line_code='CRM-01', line_name='1#轧机', workshop_name='冷轧', slot_no=1)],
        shift_rows=[
            _shift_data(
                equipment_id=None,
                shift_config_id=1,
                input_weight=4000.0,
                output_weight=3500.0,
                data_status='pending',
                data_source='mobile_coil_agg',
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T08:00:00+00:00',
        },
    )

    lines = factory_command_service.list_machine_lines(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert [item['line_code'] for item in lines] == ['CRM-01', 'workshop:1:shift:1:unbound']
    assert lines[1]['line_name'] == '未绑定机列 / 1班'
    assert lines[1]['active_tons'] == 3.5
    assert lines[1]['freshness']['source'] == 'local_shift_data'


def test_factory_machine_lines_use_latest_fill_business_date_and_reporting_machine(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='2050车间', machine_code='2050冷轧（WIFI）', net_weight=10.0),
        ],
        workshops=[SimpleNamespace(id=5, name='2050车间', code='LZ2050')],
        lines=[SimpleNamespace(line_code='2050车间:2050冷轧（wifi）', line_name='2050冷轧（WIFI）', workshop_name='2050车间', slot_no=None)],
        equipment=[
            SimpleNamespace(id=81, code='LZ2050-1-OP', name='冷轧2050车间 2050# 主操', workshop_id=5, equipment_type='virtual_role_qr', is_active=True, operational_status='running'),
            SimpleNamespace(id=123, code='LZ2050-1', name='2050轧机', workshop_id=5, equipment_type='cold_mill', is_active=True, operational_status='running'),
        ],
        shift_rows=[
            _shift_data(
                id=81,
                business_date=datetime(2026, 5, 6, 8, 0, tzinfo=UTC).date(),
                workshop_id=5,
                equipment_id=81,
                input_weight=31_642.0,
                output_weight=29_850.0,
                data_status='pending',
                data_source='mobile_coil_agg',
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-07T08:00:00+00:00',
        },
    )

    lines = factory_command_service.list_machine_lines(db, now=datetime(2026, 5, 7, 8, 1, tzinfo=UTC))

    local_line = next(item for item in lines if item['line_code'] == 'LZ2050-1')
    assert local_line['line_name'] == '2050轧机'
    assert local_line['active_tons'] == 29.85
    assert local_line['machine_binding_status'] == 'bound'
    assert not any(item['line_code'] == 'LZ2050-1-OP' for item in lines)


def test_factory_command_uses_live_fill_entries_with_mes_machine_binding(tmp_path, monkeypatch):
    db = _factory_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=datetime(2026, 5, 6, 20, 0).time(), end_time=datetime(2026, 5, 7, 8, 0).time(), is_active=True),
            ShiftConfig(id=4, code='D', name='白班', shift_type='day', start_time=datetime(2026, 5, 6, 8, 0).time(), end_time=datetime(2026, 5, 6, 20, 0).time(), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            Equipment(id=12, code='LZ2050-2', name='备用轧机', workshop_id=2, is_active=True),
            WorkOrder(id=703, tracking_card_no='RA260506703', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=703,
                work_order_id=703,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=10000.0,
                output_weight=9700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='in_progress',
                created_at=datetime(2026, 5, 7, 8, 10),
            ),
            MesCoilSnapshot(
                id=703,
                coil_id='MES-703',
                tracking_card_no='RA260506703',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=None,
                source_payload={'input_weight': 6.0, 'output_weight': 5.2, 'scrap_weight': 0.8},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {(2, 3): {'status': 'pending', 'exception_count': 0}})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-07T08:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        realtime_service.mes_sync_service,
        'latest_sync_status',
        lambda _db: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-07T08:00:00+00:00',
        },
    )
    current_user = SimpleNamespace(
        id=1,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        workshop_id=None,
        team_id=None,
        data_scope_type='all',
        assigned_shift_ids=[],
    )

    overview = factory_command_service.build_overview(
        db,
        now=datetime(2026, 5, 7, 9, 0),
        current_user=current_user,
    )
    lines = factory_command_service.list_machine_lines(
        db,
        now=datetime(2026, 5, 7, 9, 0),
        current_user=current_user,
    )
    workshops = factory_command_service.list_workshops(
        db,
        now=datetime(2026, 5, 7, 9, 0),
        current_user=current_user,
    )

    assert overview['source'] == 'mixed'
    assert overview['total_input_tons'] == 10.0
    assert overview['total_output_tons'] == 9.7
    assert overview['today_output_tons'] == 9.7
    live_line = next(item for item in lines if item['line_code'] == 'LZ2050-1')
    assert live_line['line_name'] == '2050轧机'
    assert live_line['workshop_name'] == '2050冷轧车间'
    assert live_line['active_coil_count'] == 1
    assert live_line['active_tons'] == 9.7
    assert live_line['finished_tons'] == 9.7
    assert live_line['stalled_count'] == 1
    assert live_line['machine_binding_status'] == 'bound'
    assert live_line['mes_binding'] == {
        'fill_entry_count': 1,
        'mes_matched_fill_count': 1,
        'mes_bound_fill_count': 1,
        'direct_machine_code_count': 1,
        'route_inferred_machine_count': 0,
        'mes_projection_count': 0,
    }
    assert live_line['freshness']['source'] == 'mixed'
    assert workshops == [
        {
            'workshop_name': '2050冷轧车间',
            'active_coil_count': 1,
            'active_tons': 9.7,
            'stalled_count': 1,
            'freshness': live_line['freshness'],
        }
    ]


def test_factory_command_uses_live_fill_entries_with_mes_material_code_alias(tmp_path, monkeypatch):
    db = _factory_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=datetime(2026, 5, 6, 20, 0).time(), end_time=datetime(2026, 5, 7, 8, 0).time(), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=704, tracking_card_no='S一2一054一1', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=704,
                work_order_id=704,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=10000.0,
                output_weight=9700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_at=datetime(2026, 5, 7, 8, 10),
            ),
            MesCoilSnapshot(
                id=704,
                coil_id='fallback:26RA03630:26-s-2-054-1',
                tracking_card_no='26RA03630',
                material_code='26-s-2-054-1',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=None,
                source_payload={'MaterialCode': '26-s-2-054-1'},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {(2, 3): {'status': 'pending', 'exception_count': 0}})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-07T08:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        realtime_service.mes_sync_service,
        'latest_sync_status',
        lambda _db: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-07T08:00:00+00:00',
        },
    )
    current_user = SimpleNamespace(
        id=1,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        workshop_id=None,
        team_id=None,
        data_scope_type='all',
        assigned_shift_ids=[],
    )

    overview = factory_command_service.build_overview(
        db,
        now=datetime(2026, 5, 7, 9, 0),
        current_user=current_user,
    )
    lines = factory_command_service.list_machine_lines(
        db,
        now=datetime(2026, 5, 7, 9, 0),
        current_user=current_user,
    )

    assert overview['source'] == 'mixed'
    assert overview['total_output_tons'] == 9.7
    live_line = next(item for item in lines if item['line_code'] == 'LZ2050-1')
    assert live_line['line_name'] == '2050轧机'
    assert live_line['active_tons'] == 9.7
    assert live_line['machine_binding_status'] == 'bound'


def test_factory_workshops_blend_local_mobile_coil_aggregates_when_projection_exists(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', net_weight=10.0),
        ],
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        shift_rows=[
            _shift_data(
                input_weight=4000.0,
                output_weight=3500.0,
                data_status='pending',
                data_source='mobile_coil_agg',
            ),
        ],
    )
    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'success',
            'source': 'mes_projection',
            'lag_seconds': 60,
            'last_synced_at': '2026-05-02T08:00:00+00:00',
        },
    )

    workshops = factory_command_service.list_workshops(db, now=datetime(2026, 5, 2, 8, 1, tzinfo=UTC))

    assert workshops == [
        {
            'workshop_name': '冷轧',
            'active_coil_count': 2,
            'active_tons': 13.5,
            'stalled_count': 0,
            'freshness': {
                'status': 'fresh',
                'lag_seconds': 60,
                'last_synced_at': '2026-05-02T08:00:00+00:00',
                'last_event_at': None,
                'source': 'mixed',
                'configured': True,
                'migration_ready': True,
                'action_required': 'none',
                'risk_tone': 'normal',
            },
        }
    ]


def test_workshops_and_machine_lines_group_by_current_scope(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', machine_code='冷轧:01', net_weight=10.0, delay_hours=0),
            _coil(coil_id='MES:2', current_workshop='冷轧', machine_code='冷轧:01', net_weight=5.0, delay_hours=3),
            _coil(coil_id='MES:3', current_workshop='退火', machine_code='退火:02', net_weight=7.0, delay_hours=0),
        ],
        lines=[
            SimpleNamespace(line_code='冷轧:01', line_name='1#轧机', workshop_name='冷轧', slot_no=1),
            SimpleNamespace(line_code='退火:02', line_name='2#退火炉', workshop_name='退火', slot_no=2),
        ],
    )
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 301, 'last_run_status': 'success'})

    workshops = factory_command_service.list_workshops(db)
    lines = factory_command_service.list_machine_lines(db)

    assert workshops[0]['workshop_name'] == '冷轧'
    assert workshops[0]['active_coil_count'] == 2
    assert workshops[0]['active_tons'] == 15.0
    assert lines[0]['line_code'] == '冷轧:01'
    assert lines[0]['active_coil_count'] == 2
    assert lines[0]['stalled_count'] == 1
    assert lines[0]['cost_estimate']['label'] == '经营估算'
    assert lines[0]['margin_estimate']['label'] == '毛差估算'


def test_machine_line_aliases_normalize_non_slot_machine_names(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', machine_code='1450冷轧1/2号机', net_weight=10.0),
            _coil(coil_id='MES:2', current_workshop='冷轧', machine_code='CRM-1450-1', net_weight=5.0),
        ],
        lines=[
            SimpleNamespace(
                line_code='冷轧:01',
                line_name='1#轧机',
                workshop_name='冷轧',
                slot_no=1,
                source_payload={'device_code': 'CRM-1450-1', 'source_aliases': ['1450冷轧1/2号机']},
            ),
        ],
    )
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 60})

    lines = factory_command_service.list_machine_lines(db)
    coils = factory_command_service.list_coils(db)

    assert [item['line_code'] for item in lines] == ['冷轧:01']
    assert lines[0]['active_coil_count'] == 2
    assert lines[0]['active_tons'] == 15.0
    assert {item['line_code'] for item in coils} == {'冷轧:01'}


def test_list_coils_defaults_to_bounded_page(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id=f'MES:{index}', tracking_card_no=f'BN-{index}', batch_no=f'BATCH-{index}')
            for index in range(105)
        ]
    )
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 60})

    coils = factory_command_service.list_coils(db)

    assert len(coils) == 100
    assert coils[0]['coil_key'] == 'MES:0'
    assert coils[-1]['coil_key'] == 'MES:99'


def test_list_coils_applies_filters_offset_and_limit(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', tracking_card_no='LZ-1', current_workshop='冷轧', current_process='轧制'),
            _coil(coil_id='MES:2', tracking_card_no='LZ-2', current_workshop='冷轧', current_process='轧制'),
            _coil(coil_id='MES:3', tracking_card_no='LZ-3', current_workshop='冷轧', current_process='轧制'),
            _coil(coil_id='MES:4', tracking_card_no='TH-1', current_workshop='退火', current_process='退火'),
            _coil(coil_id='MES:5', tracking_card_no='LZ-STOCK', current_workshop='冷轧', current_process=None, next_process=None, status_name='已入库', in_stock_date=datetime(2026, 5, 2, 8, 0, tzinfo=UTC)),
        ]
    )
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 60})

    coils = factory_command_service.list_coils(
        db,
        limit=2,
        offset=1,
        workshop='冷轧',
        destination='in_progress',
        query='LZ',
    )

    assert [item['coil_key'] for item in coils] == ['MES:2', 'MES:3']


def test_list_coils_pushes_filters_and_page_to_database(monkeypatch, tmp_path):
    db = _sqlalchemy_session(tmp_path)
    db.add_all(
        [
            MesCoilSnapshot(coil_id='MES:1', tracking_card_no='LZ-1', batch_no='BATCH-1', current_workshop='冷轧', current_process='轧制', next_process='退火'),
            MesCoilSnapshot(coil_id='MES:2', tracking_card_no='LZ-2', batch_no='BATCH-2', current_workshop='冷轧', current_process='轧制', next_process='退火'),
            MesCoilSnapshot(coil_id='MES:3', tracking_card_no='LZ-3', batch_no='BATCH-3', current_workshop='冷轧', current_process='轧制', next_process='退火'),
            MesCoilSnapshot(coil_id='MES:4', tracking_card_no='TH-1', batch_no='BATCH-4', current_workshop='退火', current_process='退火', next_process='精整'),
            MesCoilSnapshot(coil_id='MES:5', tracking_card_no='LZ-STOCK', batch_no='BATCH-5', current_workshop='冷轧', status_name='已入库', in_stock_date=datetime(2026, 5, 2, 8, 0, tzinfo=UTC)),
            MesCoilSnapshot(coil_id='MES:6', tracking_card_no='EMPTY-1', batch_no='BATCH-6', current_workshop='冷轧', current_process='', next_process=''),
        ]
    )
    db.commit()
    monkeypatch.setattr(factory_command_service, '_scoped_coils', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('full coil scan')))

    coils = factory_command_service.list_coils(
        db,
        limit=2,
        offset=1,
        workshop='冷轧',
        destination='in_progress',
        query='LZ',
    )

    assert [item['coil_key'] for item in coils] == ['MES:2', 'MES:3']

    unknown_coils = factory_command_service.list_coils(db, limit=10, destination='unknown', query='EMPTY')

    assert [item['coil_key'] for item in unknown_coils] == ['MES:6']


def test_factory_command_filters_projection_rows_by_workshop_scope(monkeypatch):
    scope = SimpleNamespace(is_admin=False, data_scope_type='self_workshop', workshop_id=1)
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        coils=[
            _coil(coil_id='MES:1', current_workshop='冷轧', workshop_code='LZ', machine_code='1#轧机', net_weight=10.0),
            _coil(coil_id='MES:2', current_workshop='退火', workshop_code='TH', machine_code='2#退火炉', net_weight=7.0),
        ],
        lines=[
            SimpleNamespace(line_code='冷轧:01', line_name='1#轧机', workshop_name='冷轧', slot_no=1),
            SimpleNamespace(line_code='退火:02', line_name='2#退火炉', workshop_name='退火', slot_no=2),
        ],
    )
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 60})

    overview = factory_command_service.build_overview(db, scope=scope)
    workshops = factory_command_service.list_workshops(db, scope=scope)
    lines = factory_command_service.list_machine_lines(db, scope=scope)
    coils = factory_command_service.list_coils(db, scope=scope)

    assert overview['wip_tons'] == 10.0
    assert [item['workshop_name'] for item in workshops] == ['冷轧']
    assert [item['line_code'] for item in lines] == ['冷轧:01']
    assert [item['coil_key'] for item in coils] == ['MES:1']
    assert coils[0]['line_code'] == '冷轧:01'


def test_factory_command_workshop_scope_expands_via_master_code_aliases(tmp_path, monkeypatch):
    db = _factory_realtime_session(tmp_path)
    workshop = Workshop(id=1, code='LZ2050', name='2050冷轧', sort_order=1, is_active=True)
    db.add(workshop)
    db.add_all(
        [
            MasterCodeAlias(
                entity_type='workshop',
                canonical_code='LZ2050',
                alias_code='2050车间',
                alias_name='2050车间',
                source_type='mes_mvc',
                is_active=True,
            ),
            MasterCodeAlias(
                entity_type='workshop',
                canonical_code='LZ2050',
                alias_code='冷轧2050车间',
                alias_name='冷轧2050车间',
                source_type='mes_mvc',
                is_active=True,
            ),
        ]
    )
    db.commit()

    scope = SimpleNamespace(is_admin=False, data_scope_type='self_workshop', workshop_id=1)
    tokens = factory_command_service._scope_workshop_tokens(db, scope)

    assert tokens is not None
    assert {'LZ2050', '2050冷轧', '2050车间', '冷轧2050车间'}.issubset(tokens)


def test_flow_suggestion_returns_ambiguous_status_for_duplicate_tracking_card(monkeypatch):
    db = _FakeDB(
        coils=[
            _coil(coil_id='MES:1', tracking_card_no='BN-1', batch_no='BATCH-1'),
            _coil(coil_id='MES:2', tracking_card_no='BN-1', batch_no='BATCH-2', next_process='精整'),
        ]
    )

    suggestion = factory_command_service.find_coil_flow_suggestion(db, tracking_card_no='BN-1')

    assert suggestion['flow_source'] == 'manual_pending_match'
    assert suggestion['match_status'] == 'ambiguous'
    assert suggestion['candidate_count'] == 2
    assert suggestion.get('coil_key') is None


def test_coil_flow_returns_previous_current_next_and_destination(monkeypatch):
    coil = _coil(
        coil_id='MES:1',
        current_workshop='退火',
        current_process='退火',
        next_workshop='精整',
        next_process='拉弯矫',
        allocation_date=datetime(2026, 5, 3, 8, 0, tzinfo=UTC),
    )
    event = SimpleNamespace(
        coil_key='MES:1',
        previous_workshop='冷轧',
        previous_process='轧制',
        current_workshop='退火',
        current_process='退火',
        next_workshop='精整',
        next_process='拉弯矫',
        event_time=datetime(2026, 5, 2, 8, 30, tzinfo=UTC),
    )
    db = _FakeDB(coils=[coil], events=[event])
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 901, 'last_run_status': 'failed'})

    flow = factory_command_service.get_coil_flow(db, coil_key='MES:1')

    assert flow['coil_key'] == 'MES:1'
    assert flow['previous_process'] == '轧制'
    assert flow['current_process'] == '退火'
    assert flow['next_process'] == '拉弯矫'
    assert flow['destination']['kind'] == 'allocation'
    assert flow['freshness']['status'] == 'stale'
    assert flow['freshness']['risk_tone'] == 'high'


def test_coil_flow_does_not_return_out_of_scope_event(monkeypatch):
    scope = SimpleNamespace(is_admin=False, data_scope_type='self_workshop', workshop_id=1)
    db = _FakeDB(
        workshops=[SimpleNamespace(id=1, name='冷轧', code='LZ')],
        coils=[_coil(coil_id='MES:1', current_workshop='冷轧', workshop_code='LZ')],
        events=[
            SimpleNamespace(
                coil_key='MES:2',
                previous_workshop='冷轧',
                previous_process='轧制',
                current_workshop='退火',
                current_process='退火',
                next_workshop='精整',
                next_process='拉弯矫',
                event_time=datetime(2026, 5, 2, 8, 30, tzinfo=UTC),
            )
        ],
    )
    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 60})

    flow = factory_command_service.get_coil_flow(db, coil_key='MES:2', scope=scope)

    assert flow['coil_key'] == 'MES:2'
    assert flow['previous_process'] is None
    assert flow['current_process'] is None
    assert flow['destination']['kind'] == 'unknown'


def test_freshness_thresholds(monkeypatch):
    db = _FakeDB()

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 119, 'status': 'fresh'})
    assert factory_command_service.build_freshness(db)['status'] == 'fresh'

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 301, 'status': 'fresh'})
    assert factory_command_service.build_freshness(db)['status'] == 'stale'

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 901, 'status': 'fresh'})
    high_risk = factory_command_service.build_freshness(db)
    assert high_risk['status'] == 'stale'
    assert high_risk['risk_tone'] == 'high'


def test_freshness_uses_real_time_when_overview_receives_business_date(monkeypatch):
    db = _FakeDB()
    seen_now = []

    def fake_latest_sync_status(_db, now=None):
        seen_now.append(now)
        return {'lag_seconds': 60, 'status': 'fresh'}

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', fake_latest_sync_status)

    freshness = factory_command_service.build_freshness(db, now=date(2026, 6, 1))

    assert freshness['status'] == 'fresh'
    assert seen_now == [None]


def test_freshness_preserves_unconfigured_and_migration_states(monkeypatch):
    db = _FakeDB()

    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'unconfigured',
            'configured': False,
            'migration_ready': True,
            'source': 'local_entry',
            'action_required': 'configure_mes',
            'lag_seconds': None,
        },
    )

    unconfigured = factory_command_service.build_freshness(db)

    assert unconfigured['status'] == 'unconfigured'
    assert unconfigured['source'] == 'local_entry'
    assert unconfigured['action_required'] == 'configure_mes'

    monkeypatch.setattr(
        factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {
            'status': 'migration_missing',
            'configured': True,
            'migration_ready': False,
            'source': 'local_entry',
            'action_required': 'run_migration',
            'lag_seconds': None,
        },
    )

    migration_missing = factory_command_service.build_freshness(db)

    assert migration_missing['status'] == 'migration_missing'
    assert migration_missing['migration_ready'] is False
    assert migration_missing['action_required'] == 'run_migration'
