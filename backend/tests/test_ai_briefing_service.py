from __future__ import annotations

from datetime import time
from types import SimpleNamespace

from app.models.mes import MesCoilSnapshot, MesMachineLineSnapshot
from app.services import ai_briefing_service


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, rows_by_model=None):
        self.added = []
        self.rows_by_model = rows_by_model or {}

    def query(self, model):
        return _Query(self.rows_by_model.get(model, []))

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


def test_opening_briefing_includes_wip_priority_lines_risk_and_sync(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(
        ai_briefing_service.factory_command_service,
        'build_overview',
        lambda _db: {'wip_tons': 12.0, 'abnormal_count': 2, 'freshness': {'status': 'fresh'}},
    )
    monkeypatch.setattr(
        ai_briefing_service.factory_command_service,
        'list_machine_lines',
        lambda _db: [{'line_code': '冷轧:01', 'stalled_count': 1, 'active_tons': 12.0}],
    )
    monkeypatch.setattr(ai_briefing_service.ai_rules_service, 'evaluate_rules', lambda _db: [{'key': 'delay_hours_high', 'severity': 'warning'}])

    event = ai_briefing_service.generate_briefing(db, briefing_type='opening_shift')

    assert event['briefing_type'] == 'opening_shift'
    assert event['payload']['wip_tons'] == 12.0
    assert event['payload']['priority_machine_lines'][0]['line_code'] == '冷轧:01'
    assert event['payload']['rules_fired'][0]['key'] == 'delay_hours_high'
    assert db.added


def test_hourly_inspection_can_hide_normal_items(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'build_overview', lambda _db: {'wip_tons': 12.0, 'abnormal_count': 0, 'freshness': {'status': 'fresh'}})
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'list_machine_lines', lambda _db: [{'line_code': '冷轧:01', 'stalled_count': 0}])
    monkeypatch.setattr(ai_briefing_service.ai_rules_service, 'evaluate_rules', lambda _db: [])

    event = ai_briefing_service.generate_briefing(db, briefing_type='hourly_inspection', hide_normal=True)

    assert event['payload']['normal_items'] == []
    assert event['severity'] == 'info'


def test_hourly_inspection_handles_unmatched_mes_machine_codes(monkeypatch):
    db = _FakeDB(
        {
            MesCoilSnapshot: [
                SimpleNamespace(
                    coil_id='MES:1',
                    tracking_card_no='BN-1',
                    current_workshop='2050车间',
                    current_process='冷轧',
                    next_process='退火',
                    machine_code=None,
                    net_weight=10.0,
                    delay_hours=0,
                    in_stock_date=None,
                    status_name='生产中',
                ),
                SimpleNamespace(
                    coil_id='MES:2',
                    tracking_card_no='BN-2',
                    current_workshop='冷轧',
                    current_process='冷轧',
                    next_process='退火',
                    machine_code='冷轧:01',
                    net_weight=5.0,
                    delay_hours=0,
                    in_stock_date=None,
                    status_name='生产中',
                ),
            ],
            MesMachineLineSnapshot: [
                SimpleNamespace(line_code='冷轧:01', line_name='1#轧机', workshop_name='冷轧', slot_no=1),
            ],
        }
    )
    monkeypatch.setattr(
        ai_briefing_service.factory_command_service,
        'latest_sync_status',
        lambda _db, now=None: {'lag_seconds': 60, 'last_run_status': 'success'},
    )
    monkeypatch.setattr(
        ai_briefing_service.factory_command_service,
        'build_overview',
        lambda _db: {'wip_tons': 15.0, 'abnormal_count': 0, 'freshness': {'status': 'fresh'}},
    )
    monkeypatch.setattr(ai_briefing_service.ai_rules_service, 'evaluate_rules', lambda _db: [])

    event = ai_briefing_service.generate_briefing(db, briefing_type='hourly_inspection', hide_normal=True)

    line_codes = {item['line_code'] for item in event['payload']['priority_machine_lines']}
    assert '未匹配机列:冷轧2050' in line_codes
    assert '冷轧:01' in line_codes
    assert db.added


def test_briefing_generation_uses_owner_and_scope(monkeypatch):
    db = _FakeDB()
    scope = SimpleNamespace(data_scope_type='self_workshop', workshop_id=1)
    seen = {}

    def build_overview(_db, *, scope=None):
        seen['overview_scope'] = scope
        return {'wip_tons': 3.0, 'abnormal_count': 1, 'freshness': {'status': 'fresh'}}

    def list_machine_lines(_db, *, scope=None):
        seen['line_scope'] = scope
        return [{'line_code': '冷轧:01', 'stalled_count': 1, 'active_tons': 3.0}]

    def evaluate_rules(_db, *, scope=None):
        seen['rule_scope'] = scope
        return [{'key': 'route_missing', 'severity': 'warning'}]

    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'build_overview', build_overview)
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'list_machine_lines', list_machine_lines)
    monkeypatch.setattr(ai_briefing_service.ai_rules_service, 'evaluate_rules', evaluate_rules)

    event = ai_briefing_service.generate_briefing(
        db,
        briefing_type='opening_shift',
        owner_user_id=7,
        scope=scope,
    )

    assert event['owner_user_id'] == 7
    assert seen == {'overview_scope': scope, 'line_scope': scope, 'rule_scope': scope}
    assert db.added[0].owner_user_id == 7


def test_exception_briefing_triggers_for_route_sync_weight_and_destination(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(
        ai_briefing_service.ai_rules_service,
        'evaluate_rules',
        lambda _db: [
            {'key': 'route_missing', 'severity': 'warning'},
            {'key': 'delay_hours_high', 'severity': 'warning'},
            {'key': 'sync_stale', 'severity': 'critical'},
            {'key': 'weight_anomaly', 'severity': 'warning'},
            {'key': 'destination_unknown', 'severity': 'warning'},
        ],
    )
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'build_overview', lambda _db: {'wip_tons': 0, 'abnormal_count': 5, 'freshness': {'status': 'stale'}})
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'list_machine_lines', lambda _db: [])

    event = ai_briefing_service.generate_briefing(db, briefing_type='exception_flash')

    assert event['severity'] == 'critical'
    assert {item['key'] for item in event['payload']['rules_fired']} >= {'route_missing', 'delay_hours_high', 'sync_stale', 'weight_anomaly', 'destination_unknown'}


def test_watchlist_filters_briefing_scope_and_quiet_hours_only_suppress_delivery(monkeypatch):
    db = _FakeDB()
    seen = {}
    scope = {'type': 'machine', 'key': '冷轧:01'}
    watch = SimpleNamespace(
        id=1,
        owner_user_id=7,
        watch_type='machine',
        scope_key='冷轧:01',
        trigger_rules=['delay_hours_high'],
        quiet_hours={'start': '00:00', 'end': '23:59'},
        frequency='hourly',
        channels=['in_app'],
        active=True,
    )

    def evaluate_rules(_db, *, scope=None):
        seen['rule_scope'] = scope
        return [{'key': 'delay_hours_high', 'severity': 'warning', 'evidence_refs': [{'kind': 'machine', 'key': '冷轧:01'}]}]

    monkeypatch.setattr(ai_briefing_service.ai_rules_service, 'evaluate_rules', evaluate_rules)
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'build_overview', lambda _db: {'wip_tons': 0, 'abnormal_count': 1, 'freshness': {'status': 'fresh'}})
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'list_machine_lines', lambda _db: [])

    event = ai_briefing_service.generate_watchlist_briefing(db, watch=watch, current_time=time(8, 0), scope=scope)

    assert event['briefing_type'] == 'watchlist_update'
    assert event['owner_user_id'] == 7
    assert event['scope_key'] == '冷轧:01'
    assert event['delivery_suppressed'] is True
    assert seen['rule_scope'] == scope
    assert db.added[0].owner_user_id == 7
    assert db.added
