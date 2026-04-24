import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.permissions import get_current_manager_user
from app.main import app
from app.services import assistant_service


def _override_manager_user():
    return SimpleNamespace(
        id=1,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        workshop_id=None,
        data_scope_type='all',
    )


def _force_mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENABLED', False)
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_BASE', '')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_KEY', '')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_MODEL', '')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENDPOINT_ID', '')


def test_assistant_capabilities_returns_deterministic_mock_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_mock_llm(monkeypatch)
    app.dependency_overrides[get_current_manager_user] = _override_manager_user

    client = TestClient(app)
    response = client.get('/api/v1/assistant/capabilities')

    assert response.status_code == 200
    payload = response.json()
    assert payload['connected'] is True
    assert payload['assistant_status'] == 'mock_ready'
    assert payload['capabilities'][0]['key'] == 'query'
    assert payload['capabilities'][0]['entrypoint'] == '/api/v1/assistant/query'
    assert payload['integrations'][0]['key'] == 'dashboard'
    assert payload['integrations'][-1]['key'] == 'delivery_status'
    assert payload['quick_actions'][0] == {
        'key': 'priority-blocker',
        'label': '阻塞优先级',
        'mode': 'answer',
        'query': '今天先处理哪个阻塞项最有效？',
    }
    assert payload['quick_actions'][-1] == {
        'key': 'daily-briefing-image',
        'label': '生成日报图',
        'mode': 'generate_image',
        'query': '生成今日产量和异常简报图。',
    }
    assert payload['summary_cards'] == [
        {
            'key': 'capabilities',
            'title': '能力域',
            'value': '3',
            'detail': '分析 / 执行 / 出图',
            'tone': 'primary',
        },
        {
            'key': 'integrations',
            'title': '已接数据',
            'value': '3',
            'detail': '首页 / 流程 / 交付',
            'tone': 'neutral',
        },
        {
            'key': 'agents',
            'title': '双助手',
            'value': '在线',
            'detail': '分析决策 + 执行交付',
            'tone': 'success',
        },
    ]

    app.dependency_overrides.clear()


def test_assistant_query_returns_answer_contract_for_review_home(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_mock_llm(monkeypatch)
    app.dependency_overrides[get_current_manager_user] = _override_manager_user

    client = TestClient(app)
    response = client.post(
        '/api/v1/assistant/query',
        json={
            'mode': 'answer',
            'query': '今天为什么要关注合同进度',
            'surface': 'review_home',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'answer'
    assert payload['mock'] is True
    assert payload['summary'] == '当前为 deterministic 回退，优先关注算法阻塞与交付闭环。'
    assert payload['cards'][0]['title'] == '阻塞优先级'
    assert payload['cards'][0]['source_labels'] == ['算法流水线', '执行交付助手']
    assert payload['integrations_used'] == ['dashboard', 'runtime_trace', 'delivery_status']
    assert payload['next_actions'] == ['查看阻塞清单', '触发交付检查', '生成简报卡']

    app.dependency_overrides.clear()


@pytest.mark.parametrize('mode', ['answer', 'search', 'retrieve', 'automation'])
def test_assistant_query_supports_all_agent_modes(mode: str) -> None:
    app.dependency_overrides[get_current_manager_user] = _override_manager_user

    client = TestClient(app)
    response = client.post(
        '/api/v1/assistant/query',
        json={
            'mode': mode,
            'query': f'测试模式 {mode}',
            'surface': 'review_home',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == mode
    assert isinstance(payload['summary'], str)
    assert payload['summary']
    assert isinstance(payload['cards'], list) and payload['cards']

    app.dependency_overrides.clear()


def test_assistant_generate_image_returns_mock_preview_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_mock_llm(monkeypatch)
    app.dependency_overrides[get_current_manager_user] = _override_manager_user

    client = TestClient(app)
    response = client.post(
        '/api/v1/assistant/generate-image',
        json={
            'prompt': '生成今日产量与异常的简报图',
            'image_type': 'daily_briefing_card',
            'surface': 'review_home',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mock'] is True
    assert payload['image_type'] == 'daily_briefing_card'
    assert payload['asset_id'] == 'mock-daily-briefing-card'
    assert payload['image_url'].startswith('data:image/svg+xml;utf8,')
    assert payload['suggested_caption'] == '今日产量、异常和交付风险简报图（mock）'
    assert payload['next_actions'] == ['保存到日报卡片', '推送到审阅首页', '继续调用真实图像生成']

    app.dependency_overrides.clear()


def test_assistant_capabilities_switch_to_live_when_llm_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_manager_user] = _override_manager_user
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENABLED', True)
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_BASE', 'https://ark.cn-beijing.volces.com/api/v3')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_KEY', 'test-volc-key')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_MODEL', 'DeepSeek-V3.2')

    client = TestClient(app)
    response = client.get('/api/v1/assistant/capabilities')

    assert response.status_code == 200
    payload = response.json()
    assert payload['assistant_status'] == 'live'
    assert payload['summary_cards'][-1]['value'] == '在线'
    assert payload['integrations'][0]['status'] == 'live'

    app.dependency_overrides.clear()


def test_assistant_capabilities_switch_to_live_when_endpoint_id_only(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_manager_user] = _override_manager_user
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENABLED', True)
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_BASE', 'https://ark.cn-beijing.volces.com/api/v3')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_KEY', 'test-volc-key')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_MODEL', '')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENDPOINT_ID', 'ep-test-001')

    client = TestClient(app)
    response = client.get('/api/v1/assistant/capabilities')

    assert response.status_code == 200
    payload = response.json()
    assert payload['assistant_status'] == 'live'
    assert payload['integrations'][0]['status'] == 'live'

    app.dependency_overrides.clear()


def test_assistant_query_uses_llm_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_manager_user] = _override_manager_user
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENABLED', True)
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_BASE', 'https://ark.cn-beijing.volces.com/api/v3')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_KEY', 'test-volc-key')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_MODEL', 'DeepSeek-V3.2')
    monkeypatch.setattr(
        assistant_service,
        'generate_llm_summary',
        lambda **_kwargs: json.dumps(
            {
                'summary': '已通过火山引擎 DeepSeek-V3.2 生成摘要。',
                'cards': [
                    {
                        'title': '产线关注',
                        'summary': '优先处理退回与缺报链路。',
                        'source_labels': ['系统汇总', '结果发布'],
                    }
                ],
                'next_actions': ['先清缺报', '再看交付', '最后归档'],
                'integrations_used': ['dashboard', 'history_digest', 'runtime_trace'],
            },
            ensure_ascii=False,
        ),
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/assistant/query',
        json={
            'mode': 'retrieve',
            'query': '整理今天关键上下文',
            'surface': 'review_home',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mock'] is False
    assert payload['mode'] == 'retrieve'
    assert payload['summary'] == '已通过火山引擎 DeepSeek-V3.2 生成摘要。'
    assert payload['cards'][0]['title'] == '产线关注'
    assert payload['integrations_used'] == ['dashboard', 'history_digest', 'runtime_trace']

    app.dependency_overrides.clear()


def test_assistant_generate_image_uses_llm_caption_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_manager_user] = _override_manager_user
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENABLED', True)
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_BASE', 'https://ark.cn-beijing.volces.com/api/v3')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_KEY', 'test-volc-key')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_MODEL', 'DeepSeek-V3.2')
    monkeypatch.setattr(
        assistant_service,
        'generate_llm_summary',
        lambda **_kwargs: json.dumps(
            {
                'caption': 'DeepSeek-V3.2 生成：先看缺报与退回，再压交付风险。',
                'next_actions': ['推送厂级看板', '同步到日报卡片'],
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setattr(
        assistant_service,
        'generate_llm_image_asset',
        lambda **_kwargs: {
            'image_url': 'https://example.invalid/daily-briefing.png',
            'model': 'deepseek-v3-2-image',
        },
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/assistant/generate-image',
        json={
            'prompt': '生成今日产量与异常的简报图',
            'image_type': 'daily_briefing_card',
            'surface': 'review_home',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mock'] is False
    assert payload['asset_id'] == 'daily-briefing-card-llm'
    assert payload['image_url'] == 'https://example.invalid/daily-briefing.png'
    assert payload['suggested_caption'].startswith('DeepSeek-V3.2 生成')
    assert payload['next_actions'] == ['推送厂级看板', '同步到日报卡片']

    app.dependency_overrides.clear()


def test_assistant_live_probe_returns_not_ready_when_llm_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_mock_llm(monkeypatch)
    app.dependency_overrides[get_current_manager_user] = _override_manager_user

    client = TestClient(app)
    response = client.get('/api/v1/assistant/live-probe')

    assert response.status_code == 200
    payload = response.json()
    assert payload['ready'] is False
    assert payload['overall_ok'] is False
    assert payload['text_probe_ok'] is False
    assert payload['image_probe_ok'] is False
    assert payload['errors']

    app.dependency_overrides.clear()


def test_assistant_live_probe_passes_when_llm_and_image_generation_available(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_manager_user] = _override_manager_user
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENABLED', True)
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_BASE', 'https://ark.cn-beijing.volces.com/api/v3')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_API_KEY', 'test-volc-key')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_MODEL', 'DeepSeek-V3.2')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_ENDPOINT_ID', 'ep-test-001')
    monkeypatch.setattr(assistant_service.runtime_settings, 'LLM_IMAGE_MODEL', 'doubao-seedream-3-0-t2i-250415')
    monkeypatch.setattr(
        assistant_service,
        'generate_llm_summary',
        lambda **_kwargs: 'live-probe-ok',
    )
    monkeypatch.setattr(
        assistant_service,
        'generate_llm_image_asset',
        lambda **_kwargs: {
            'image_url': 'https://example.invalid/live-probe.png',
            'model': 'doubao-seedream-3-0-t2i-250415',
        },
    )

    client = TestClient(app)
    response = client.get('/api/v1/assistant/live-probe')

    assert response.status_code == 200
    payload = response.json()
    assert payload['ready'] is True
    assert payload['text_probe_ok'] is True
    assert payload['image_probe_ok'] is True
    assert payload['overall_ok'] is True
    assert payload['errors'] == []

    app.dependency_overrides.clear()
