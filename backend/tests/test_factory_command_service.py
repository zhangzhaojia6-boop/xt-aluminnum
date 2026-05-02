from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.models.mes import CoilFlowEvent, MesCoilSnapshot, MesMachineLineSnapshot
from app.services import factory_command_service


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
    def __init__(self, *, coils=None, lines=None, events=None):
        self.coils = coils or []
        self.lines = lines or []
        self.events = events or []

    def query(self, model):
        if model is MesCoilSnapshot:
            return _Query(self.coils)
        if model is MesMachineLineSnapshot:
            return _Query(self.lines)
        if model is CoilFlowEvent:
            return _Query(self.events)
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
    assert overview['stock_tons'] == 2.0
    assert overview['abnormal_count'] == 2
    assert overview['cost_estimate']['label'] == '经营估算'
    assert 'profit' not in ''.join(overview['cost_estimate'].keys()).lower()
    assert overview['missing_data'] == ['cost_inputs']


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
    assert flow['freshness']['status'] == 'offline_or_blocked'


def test_freshness_thresholds(monkeypatch):
    db = _FakeDB()

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 119})
    assert factory_command_service.build_freshness(db)['status'] == 'fresh'

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 301})
    assert factory_command_service.build_freshness(db)['status'] == 'stale'

    monkeypatch.setattr(factory_command_service, 'latest_sync_status', lambda _db, now=None: {'lag_seconds': 901})
    assert factory_command_service.build_freshness(db)['status'] == 'offline_or_blocked'
