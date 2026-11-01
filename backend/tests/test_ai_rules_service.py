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


def test_route_rule_only_flags_coils_whose_route_continues_without_a_next_step(monkeypatch):
    coils = [
        # 已到路线最后一道（包装），没有下道是正常的
        {'coil_key': 'MES:LAST', 'current_process': '包装', 'next_process': None, 'process_route_text': '拉矫车间(洗拉)(505纸芯6T/C)-拉矫车间(包装)', 'destination': {'kind': 'in_progress'}},
        # 还没开工
        {'coil_key': 'MES:WAIT', 'current_process': None, 'next_process': '冷轧', 'process_route_text': '2050车间(冷轧)-精整(包装)', 'destination': {'kind': 'in_progress'}},
        # 路线后面还有剪切、包装，却没有下道工序
        {'coil_key': 'MES:GAP', 'current_process': '北线退火', 'next_process': None, 'process_route_text': '2050车间(冷轧)-新厂在线车间(北线退火)-精整(剪切)-精整(包装)', 'destination': {'kind': 'in_progress'}},
        # 已入库
        {'coil_key': 'MES:STOCK', 'current_process': '剪切', 'next_process': None, 'process_route_text': '精整(剪切)-精整(包装)', 'destination': {'kind': 'finished_stock'}},
    ]
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'fresh'})
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'list_coils', lambda _db, scope=None: coils)
    monkeypatch.setattr(ai_rules_service.factory_command_service, 'build_overview', lambda _db, scope=None: {})

    rules = ai_rules_service.evaluate_rules(object())

    assert [(rule['key'], rule['evidence_refs']) for rule in rules] == [('route_missing', [{'kind': 'coil', 'key': 'MES:GAP'}])]
