import json

import httpx

from app.adapters.llm import generate_llm_image_asset, generate_llm_summary
from app.config import Settings


def _build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'LLM_API_BASE': 'https://ark.cn-beijing.volces.com/api/v3',
        'LLM_API_KEY': 'test-key',
        'LLM_MODEL': 'DeepSeek-V3.2',
        'LLM_TIMEOUT_SECONDS': 5,
    }
    values.update(overrides)
    return Settings(**values)


def test_generate_llm_summary_prefers_endpoint_id_over_model_alias() -> None:
    called_models: list[str] = []
    models_endpoint_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal models_endpoint_called
        if request.url.path.endswith('/models'):
            models_endpoint_called = True
            return httpx.Response(500, json={'error': 'should not call /models'})
        if request.url.path.endswith('/chat/completions'):
            payload = json.loads(request.content.decode('utf-8'))
            called_models.append(str(payload.get('model')))
            return httpx.Response(200, json={'choices': [{'message': {'content': 'OK-ENDPOINT'}}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        output = generate_llm_summary(
            messages=[{'role': 'user', 'content': 'ping'}],
            settings=_build_settings(LLM_ENDPOINT_ID='ep-deepseek-v3-2'),
            client=client,
        )

    assert output == 'OK-ENDPOINT'
    assert called_models == ['ep-deepseek-v3-2']
    assert models_endpoint_called is False


def test_generate_llm_summary_resolves_deepseek_alias_after_not_found() -> None:
    called_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/models'):
            return httpx.Response(
                200,
                json={
                    'data': [
                        {'id': 'deepseek-v3-241226', 'name': 'deepseek-v3', 'created': 1738595048, 'status': 'Shutdown'},
                        {'id': 'deepseek-v3-2-251201', 'name': 'deepseek-v3-2', 'created': 1764681612},
                    ]
                },
            )
        if request.url.path.endswith('/chat/completions'):
            payload = json.loads(request.content.decode('utf-8'))
            model = str(payload.get('model'))
            called_models.append(model)
            if model == 'DeepSeek-V3.2':
                return httpx.Response(
                    404,
                    json={
                        'error': {
                            'code': 'InvalidEndpointOrModel.NotFound',
                            'message': 'model not found',
                        }
                    },
                )
            if model == 'deepseek-v3-2-251201':
                return httpx.Response(200, json={'choices': [{'message': {'content': 'OK-ALIAS'}}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        output = generate_llm_summary(
            messages=[{'role': 'user', 'content': 'ping'}],
            settings=_build_settings(LLM_ENDPOINT_ID=''),
            client=client,
        )

    assert output == 'OK-ALIAS'
    assert called_models == ['DeepSeek-V3.2', 'deepseek-v3-2-251201']


def test_generate_llm_image_asset_prefers_direct_url() -> None:
    called_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/images/generations'):
            payload = json.loads(request.content.decode('utf-8'))
            called_models.append(str(payload.get('model')))
            return httpx.Response(
                200,
                json={
                    'data': [
                        {
                            'url': 'https://example.invalid/card.png',
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        payload = generate_llm_image_asset(
            prompt='生成日报图卡',
            settings=_build_settings(LLM_IMAGE_MODEL='doubao-seedream-3-0-t2i-250415'),
            client=client,
        )

    assert payload['image_url'] == 'https://example.invalid/card.png'
    assert called_models == ['doubao-seedream-3-0-t2i-250415']


def test_generate_llm_image_asset_supports_base64_payload() -> None:
    fake_base64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/images/generations'):
            return httpx.Response(
                200,
                json={
                    'data': [
                        {
                            'b64_json': fake_base64,
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        payload = generate_llm_image_asset(
            prompt='生成异常图卡',
            settings=_build_settings(),
            client=client,
        )

    assert payload['image_url'] == f'data:image/png;base64,{fake_base64}'


def test_generate_llm_image_asset_resolves_alias_after_not_found() -> None:
    called_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/models'):
            return httpx.Response(
                200,
                json={
                    'data': [
                        {'id': 'deepseek-v3-241226', 'name': 'deepseek-v3', 'created': 1738595048, 'status': 'Shutdown'},
                        {'id': 'deepseek-v3-2-251201', 'name': 'deepseek-v3-2', 'created': 1764681612},
                    ]
                },
            )
        if request.url.path.endswith('/images/generations'):
            payload = json.loads(request.content.decode('utf-8'))
            model = str(payload.get('model'))
            called_models.append(model)
            if model == 'DeepSeek-V3.2':
                return httpx.Response(
                    404,
                    json={
                        'error': {
                            'code': 'InvalidEndpointOrModel.NotFound',
                            'message': 'image model not found',
                        }
                    },
                )
            if model == 'deepseek-v3-2-251201':
                return httpx.Response(200, json={'data': [{'url': 'https://example.invalid/alias-image.png'}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        payload = generate_llm_image_asset(
            prompt='生成今日管理简报图',
            settings=_build_settings(LLM_ENDPOINT_ID='', LLM_IMAGE_ENDPOINT_ID='', LLM_IMAGE_MODEL='DeepSeek-V3.2'),
            client=client,
        )

    assert payload['image_url'] == 'https://example.invalid/alias-image.png'
    assert called_models == ['DeepSeek-V3.2', 'deepseek-v3-2-251201']


def test_generate_llm_image_asset_discovers_image_model_after_invalid_parameter() -> None:
    called_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/models'):
            return httpx.Response(
                200,
                json={
                    'data': [
                        {'id': 'deepseek-v3-2-251201', 'name': 'deepseek-v3-2', 'created': 1764681612},
                        {'id': 'doubao-seedream-3-0-t2i-250415', 'name': 'doubao-seedream-3-0-t2i', 'created': 1768000000},
                    ]
                },
            )
        if request.url.path.endswith('/images/generations'):
            payload = json.loads(request.content.decode('utf-8'))
            model = str(payload.get('model'))
            called_models.append(model)
            if model == 'DeepSeek-V3.2':
                return httpx.Response(
                    400,
                    json={
                        'error': {
                            'code': 'InvalidParameter',
                            'message': 'image generation is only supported by certain models',
                        }
                    },
                )
            if model == 'doubao-seedream-3-0-t2i-250415':
                return httpx.Response(200, json={'data': [{'url': 'https://example.invalid/discovered-image.png'}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        payload = generate_llm_image_asset(
            prompt='生成今日产线简报图',
            settings=_build_settings(LLM_IMAGE_MODEL='', LLM_IMAGE_ENDPOINT_ID='', LLM_ENDPOINT_ID=''),
            client=client,
        )

    assert payload['image_url'] == 'https://example.invalid/discovered-image.png'
    assert called_models == ['DeepSeek-V3.2', 'doubao-seedream-3-0-t2i-250415']


def test_generate_llm_image_asset_retries_with_larger_size_when_model_requires_it() -> None:
    called_payloads: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/models'):
            return httpx.Response(
                200,
                json={
                    'data': [
                        {'id': 'doubao-seedream-3-0-t2i-250415', 'name': 'doubao-seedream-3-0-t2i', 'created': 1768000000},
                    ]
                },
            )
        if request.url.path.endswith('/images/generations'):
            payload = json.loads(request.content.decode('utf-8'))
            called_payloads.append({'model': str(payload.get('model')), 'size': str(payload.get('size'))})
            if payload.get('model') == 'DeepSeek-V3.2':
                return httpx.Response(
                    400,
                    json={'error': {'code': 'InvalidParameter', 'message': 'image generation is only supported by certain models'}},
                )
            if payload.get('model') == 'doubao-seedream-3-0-t2i-250415' and payload.get('size') == '1536x1024':
                return httpx.Response(
                    400,
                    json={'error': {'code': 'InvalidParameter', 'message': 'image size must be at least 3686400 pixels'}},
                )
            if payload.get('model') == 'doubao-seedream-3-0-t2i-250415' and payload.get('size') == '1920x1920':
                return httpx.Response(200, json={'data': [{'url': 'https://example.invalid/high-res-image.png'}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        payload = generate_llm_image_asset(
            prompt='生成今日产线简报图',
            settings=_build_settings(LLM_IMAGE_MODEL='', LLM_IMAGE_ENDPOINT_ID='', LLM_ENDPOINT_ID=''),
            client=client,
        )

    assert payload['image_url'] == 'https://example.invalid/high-res-image.png'
    assert called_payloads == [
        {'model': 'DeepSeek-V3.2', 'size': '1536x1024'},
        {'model': 'doubao-seedream-3-0-t2i-250415', 'size': '1536x1024'},
        {'model': 'doubao-seedream-3-0-t2i-250415', 'size': '1920x1920'},
    ]
