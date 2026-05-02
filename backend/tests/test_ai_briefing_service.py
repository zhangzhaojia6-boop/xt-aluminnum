from __future__ import annotations

from datetime import time
from types import SimpleNamespace

from app.services import ai_briefing_service


class _FakeDB:
    def __init__(self):
        self.added = []

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
    watch = SimpleNamespace(
        id=1,
        watch_type='machine',
        scope_key='冷轧:01',
        trigger_rules=['delay_hours_high'],
        quiet_hours={'start': '00:00', 'end': '23:59'},
        frequency='hourly',
        channels=['in_app'],
        active=True,
    )
    monkeypatch.setattr(ai_briefing_service.ai_rules_service, 'evaluate_rules', lambda _db: [{'key': 'delay_hours_high', 'severity': 'warning', 'evidence_refs': [{'kind': 'machine', 'key': '冷轧:01'}]}])
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'build_overview', lambda _db: {'wip_tons': 0, 'abnormal_count': 1, 'freshness': {'status': 'fresh'}})
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'list_machine_lines', lambda _db: [])

    event = ai_briefing_service.generate_watchlist_briefing(db, watch=watch, current_time=time(8, 0))

    assert event['briefing_type'] == 'watchlist_update'
    assert event['scope_key'] == '冷轧:01'
    assert event['delivery_suppressed'] is True
    assert db.added
