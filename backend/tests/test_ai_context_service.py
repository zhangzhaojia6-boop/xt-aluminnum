from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services import ai_context_service


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


def test_context_pack_includes_factory_scope_and_excludes_sensitive_fields(monkeypatch):
    db = _FakeDB()
    freshness = {'status': 'fresh', 'lag_seconds': 60, 'source': 'mes_projection'}
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: freshness)
    monkeypatch.setattr(
        ai_context_service.factory_command_service,
        'list_machine_lines',
        lambda _db: [{'line_code': '冷轧:01', 'active_coil_count': 2, 'stalled_count': 1, 'source_payload': {'Password': 'secret'}}],
    )
    monkeypatch.setattr(
        ai_context_service.factory_command_service,
        'list_coils',
        lambda _db: [
            {
                'coil_key': 'MES:1',
                'tracking_card_no': 'BN-1',
                'machine_code': '1#轧机',
                'line_code': '冷轧:01',
                'current_process': '轧制',
                'delay_hours': 4,
                'source_payload': {'token': 'secret'},
            },
            {'coil_key': 'MES:2', 'tracking_card_no': 'BN-2', 'current_process': '退火', 'delay_hours': 0},
        ],
    )

    pack = ai_context_service.build_context_pack(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        intent='factory_status',
        scope={'type': 'machine', 'key': '冷轧:01'},
        now=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
    )

    assert pack['scope'] == {'type': 'machine', 'key': '冷轧:01'}
    assert pack['freshness'] == freshness
    assert pack['top_abnormal_coils'][0]['coil_key'] == 'MES:1'
    assert pack['machine_line_metrics'][0]['line_code'] == '冷轧:01'
    assert pack['route_refs']
    assert pack['rules_fired'][0]['key'] == 'delay_hours_high'
    assert 'secret' not in repr(pack)
    assert db.added


def test_stale_mes_data_adds_missing_data_and_limits_confidence(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'stale', 'lag_seconds': 360})
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_coils', lambda _db: [])

    answer = ai_context_service.answer_from_context(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        question='现在异常是什么？',
        intent='factory_status',
        scope={'type': 'factory', 'key': 'all'},
    )

    assert answer['answer']
    assert answer['confidence'] == 'medium'
    assert 'mes_stale' in answer['missing_data']
    assert {'answer', 'confidence', 'evidence_refs', 'missing_data', 'recommended_next_actions', 'can_create_watch'} <= set(answer)
