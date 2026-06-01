from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.adapters.llm import LlmTextResponse
from app.config import Settings
from app.models.assistant_usage import AssistantUsage
from app.services import ai_context_service


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


def _llm_settings(**overrides):
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'sqlite:///:memory:',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'LLM_ENABLED': True,
        'LLM_API_BASE': 'https://llm.example.invalid/v1',
        'LLM_API_KEY': 'key',
        'LLM_MODEL': 'deepseek-v3',
        'LLM_DAILY_QUERY_LIMIT': 5,
    }
    values.update(overrides)
    return Settings(**values)


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


def test_failed_mes_data_is_low_confidence_and_fires_sync_rule(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'failed', 'lag_seconds': None})
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_coils', lambda _db: [])

    answer = ai_context_service.answer_from_context(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        question='现在异常是什么？',
        intent='factory_status',
        scope={'type': 'factory', 'key': 'all'},
    )
    pack = db.added[0].payload

    assert answer['confidence'] == 'low'
    assert 'mes_failed' in answer['missing_data']
    assert pack['rules_fired'][0]['key'] == 'sync_stale'
    assert pack['rules_fired'][0]['severity'] == 'critical'


def test_unconfigured_mes_data_is_medium_confidence(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'unconfigured', 'lag_seconds': None})
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_coils', lambda _db: [])

    answer = ai_context_service.answer_from_context(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        question='现在异常是什么？',
        intent='factory_status',
        scope={'type': 'factory', 'key': 'all'},
    )

    assert answer['confidence'] == 'medium'
    assert 'mes_unconfigured' in answer['missing_data']


def test_offline_mes_data_is_low_confidence(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'offline_or_blocked', 'lag_seconds': None})
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_coils', lambda _db: [])

    answer = ai_context_service.answer_from_context(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        question='现在异常是什么？',
        intent='factory_status',
        scope={'type': 'factory', 'key': 'all'},
    )

    assert answer['confidence'] == 'low'
    assert 'mes_offline' in answer['missing_data']


def test_answer_from_context_uses_llm_only_after_grounded_pack(monkeypatch):
    db = _FakeDB()
    captured = {}
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'fresh', 'lag_seconds': 30})
    monkeypatch.setattr(
        ai_context_service.factory_command_service,
        'list_machine_lines',
        lambda _db: [{'line_code': '冷轧:01', 'active_coil_count': 2, 'source_payload': {'api_key': 'secret'}}],
    )
    monkeypatch.setattr(
        ai_context_service.factory_command_service,
        'list_coils',
        lambda _db: [{'coil_key': 'MES:1', 'line_code': '冷轧:01', 'current_process': '轧制', 'delay_hours': 4}],
    )

    def fake_llm(**kwargs):
        captured['messages'] = kwargs['messages']
        return LlmTextResponse(
            content='{"answer":"AI 总管建议先看冷轧:01 的停滞卷，并核对下一工序资源。","recommended_next_actions":["查看证据卷","确认下一工序资源"]}',
            input_tokens=10,
            output_tokens=9,
            total_tokens=19,
            raw_usage={'total_tokens': 19},
        )

    monkeypatch.setattr(ai_context_service, 'generate_llm_summary_with_usage', fake_llm)

    answer = ai_context_service.answer_from_context(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        question='今天先看哪里？',
        intent='factory_status',
        scope={'type': 'machine', 'key': '冷轧:01'},
        settings=_llm_settings(),
    )

    prompt = '\n'.join(item['content'] for item in captured['messages'])
    assert answer['answer'].startswith('AI 总管建议')
    assert answer['recommended_next_actions'] == ['查看证据卷', '确认下一工序资源']
    assert answer['confidence'] == 'high'
    assert 'secret' not in prompt
    assert 'DETERMINISTIC_ANSWER' in prompt
    assert 'SAFE_CONTEXT' in prompt


def test_answer_from_context_falls_back_when_llm_is_unconfigured(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'fresh', 'lag_seconds': 30})
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_coils', lambda _db: [])

    def fail_llm(**_kwargs):
        raise AssertionError('LLM should not be called when disabled')

    monkeypatch.setattr(ai_context_service, 'generate_llm_summary_with_usage', fail_llm)

    answer = ai_context_service.answer_from_context(
        db,
        user=SimpleNamespace(id=7, data_scope_type='all'),
        question='今天先看哪里？',
        settings=_llm_settings(LLM_ENABLED=False),
    )

    assert answer['answer'] == '当前上下文未发现明确异常，建议继续查看同步新鲜度和机列负荷。'


def test_answer_from_context_records_usage_and_respects_daily_limit(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models.assistant import AiContextPack
    from app.models.system import User

    engine = create_engine(f"sqlite:///{tmp_path / 'ai-context-usage.db'}", future=True)
    Base.metadata.create_all(engine, tables=[User.__table__, AssistantUsage.__table__, AiContextPack.__table__])
    db = sessionmaker(bind=engine, future=True)()
    user = User(username='manager', password_hash='x', name='Manager', role='manager', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    monkeypatch.setattr(ai_context_service.factory_command_service, 'build_freshness', lambda _db: {'status': 'fresh', 'lag_seconds': 30})
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_machine_lines', lambda _db: [])
    monkeypatch.setattr(ai_context_service.factory_command_service, 'list_coils', lambda _db: [])
    monkeypatch.setattr(
        ai_context_service,
        'generate_llm_summary_with_usage',
        lambda **_kwargs: LlmTextResponse(content='{"answer":"已基于上下文回答。"}', input_tokens=1, output_tokens=2, total_tokens=3, raw_usage={}),
    )

    try:
        answer = ai_context_service.answer_from_context(
            db,
            user=user,
            question='今天先看哪里？',
            settings=_llm_settings(LLM_DAILY_QUERY_LIMIT=1),
        )
        assert answer['answer'] == '已基于上下文回答。'
        assert db.query(AssistantUsage).count() == 1

        limited = ai_context_service.answer_from_context(
            db,
            user=user,
            question='继续问',
            settings=_llm_settings(LLM_DAILY_QUERY_LIMIT=1),
        )
        assert limited['answer'] == '当前上下文未发现明确异常，建议继续查看同步新鲜度和机列负荷。'
        assert db.query(AssistantUsage).count() == 1
    finally:
        db.close()
