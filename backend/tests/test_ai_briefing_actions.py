from __future__ import annotations

from app.services import ai_briefing_service


class _FakeDB:
    def add(self, _value):
        return None

    def flush(self):
        return None


def test_generate_briefing_adds_suggested_actions_to_machine_actionable_rules(monkeypatch) -> None:
    db = _FakeDB()
    monkeypatch.setattr(
        ai_briefing_service.factory_command_service,
        'build_overview',
        lambda _db: {'wip_tons': 0, 'abnormal_count': 2, 'freshness': {'status': 'fresh'}},
    )
    monkeypatch.setattr(ai_briefing_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(
        ai_briefing_service.ai_rules_service,
        'evaluate_rules',
        lambda _db: [
            {
                'key': 'returned_report',
                'severity': 'warning',
                'report_id': 101,
                'shift_config_id': 7,
                'target_date': '2026-05-03',
                'evidence_refs': [{'kind': 'mobile_shift_report', 'key': '101'}],
            },
            {
                'key': 'weight_anomaly',
                'severity': 'warning',
                'target_date': '2026-05-03',
                'evidence_refs': [{'kind': 'shift_production_data', 'key': '2026-05-03'}],
            },
            {'key': 'cost_estimate_missing', 'severity': 'info'},
        ],
    )

    event = ai_briefing_service.generate_briefing(db, briefing_type='hourly_inspection')
    rules = {item['key']: item for item in event['payload']['rules_fired']}

    returned_actions = rules['returned_report']['suggested_actions']
    assert [item['action'] for item in returned_actions] == ['call_validator', 'call_reminder']
    assert returned_actions[0]['target_type'] == 'mobile_shift_report'
    assert returned_actions[0]['target_id'] == 101
    assert returned_actions[1]['target_type'] == 'shift_config'
    assert returned_actions[1]['target_id'] == 7
    assert rules['weight_anomaly']['suggested_actions'][0]['action'] == 'call_reconciler'
    assert rules['cost_estimate_missing']['suggested_actions'] == []

