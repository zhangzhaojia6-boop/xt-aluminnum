from __future__ import annotations

from app.services import ai_rules_service


def test_sync_projection_migration_missing_fires_critical_rule(monkeypatch):
    monkeypatch.setattr(
        ai_rules_service.factory_command_service,
        'build_freshness',
        lambda _db: {'status': 'migration_missing', 'lag_seconds': None, 'action_required': 'run_migration'},
    )
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'list_coils', lambda _db, scope=None: [])
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'build_overview', lambda _db, scope=None: {})

    rules = ai_rules_service.evaluate_rules(object())

    assert rules[0]['key'] == 'sync_stale'
    assert rules[0]['severity'] == 'critical'
    assert rules[0]['evidence_refs'] == [{'kind': 'sync', 'key': 'mes_projection'}]


def test_sync_unconfigured_fires_warning_rule(monkeypatch):
    monkeypatch.setattr(
        ai_rules_service.factory_command_service,
        'build_freshness',
        lambda _db: {'status': 'unconfigured', 'lag_seconds': None, 'action_required': 'configure_mes'},
    )
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'list_coils', lambda _db, scope=None: [])
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'build_overview', lambda _db, scope=None: {})

    rules = ai_rules_service.evaluate_rules(object())

    assert rules[0]['key'] == 'sync_stale'
    assert rules[0]['severity'] == 'warning'


def test_sync_offline_fires_critical_rule(monkeypatch):
    monkeypatch.setattr(
        ai_rules_service.factory_command_service,
        'build_freshness',
        lambda _db: {'status': 'offline_or_blocked', 'lag_seconds': None},
    )
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'list_coils', lambda _db, scope=None: [])
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'build_overview', lambda _db, scope=None: {})

    rules = ai_rules_service.evaluate_rules(object())

    assert rules[0]['key'] == 'sync_stale'
    assert rules[0]['severity'] == 'critical'
