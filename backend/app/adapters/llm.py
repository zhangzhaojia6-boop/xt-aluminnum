from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import Settings, settings as runtime_settings


def _completion_url(base_url: str) -> str:
    normalized = str(base_url or '').rstrip('/')
    if normalized.endswith('/chat/completions'):
        return normalized
    return f'{normalized}/chat/completions'


def _models_url(base_url: str) -> str:
    normalized = str(base_url or '').rstrip('/')
    if normalized.endswith('/models'):
        return normalized
    return f'{normalized}/models'


def _images_url(base_url: str) -> str:
    normalized = str(base_url or '').rstrip('/')
    if normalized.endswith('/images/generations'):
        return normalized
    return f'{normalized}/images/generations'


def _canonical_model_token(value: str) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return ''
    normalized = text.replace('_', '-').replace('.', '-')
    normalized = re.sub(r'[^a-z0-9-]+', '', normalized)
    normalized = re.sub(r'-{2,}', '-', normalized).strip('-')
    return normalized


def _extract_error_code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(body, dict):
        return None
    error_obj = body.get('error')
    if not isinstance(error_obj, dict):
        return None
    code = error_obj.get('code')
    if not isinstance(code, str):
        return None
    return code.strip() or None


def _extract_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return ''
    if not isinstance(body, dict):
        return ''
    error_obj = body.get('error')
    if not isinstance(error_obj, dict):
        return ''
    message = error_obj.get('message')
    if not isinstance(message, str):
        return ''
    return message.strip()


def _resolve_model_alias(
    *,
    base_url: str,
    headers: dict[str, str],
    alias: str,
    client: httpx.Client,
) -> str | None:
    alias_key = _canonical_model_token(alias)
    if not alias_key:
        return None

    try:
        response = client.get(_models_url(base_url), headers=headers)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    except Exception:  # noqa: BLE001
        return None

    models = body.get('data') if isinstance(body, dict) else None
    if not isinstance(models, list):
        return None

    candidates: list[tuple[int, int, str]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get('id') or '').strip()
        model_name = str(item.get('name') or '').strip()
        if not model_id:
            continue

        model_id_key = _canonical_model_token(model_id)
        model_name_key = _canonical_model_token(model_name)
        matched = any(
            (
                model_id_key == alias_key,
                model_name_key == alias_key,
                model_id_key.startswith(f'{alias_key}-'),
                model_name_key.startswith(f'{alias_key}-'),
            )
        )
        if not matched:
            continue

        created = int(item.get('created') or 0)
        status = str(item.get('status') or '').strip().lower()
        status_score = 0 if status == 'shutdown' else 1
        candidates.append((status_score, created, model_id))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][2]


def _resolve_latest_image_model(
    *,
    base_url: str,
    headers: dict[str, str],
    client: httpx.Client,
) -> str | None:
    try:
        response = client.get(_models_url(base_url), headers=headers)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    except Exception:  # noqa: BLE001
        return None

    models = body.get('data') if isinstance(body, dict) else None
    if not isinstance(models, list):
        return None

    image_signals = ('seedream', 't2i', 'image', 'img')
    candidates: list[tuple[int, int, str]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get('id') or '').strip()
        model_name = str(item.get('name') or '').strip()
        if not model_id:
            continue

        id_key = _canonical_model_token(model_id)
        name_key = _canonical_model_token(model_name)
        is_image_candidate = any(
            signal in id_key or signal in name_key
            for signal in image_signals
        )
        if not is_image_candidate:
            continue

        created = int(item.get('created') or 0)
        status = str(item.get('status') or '').strip().lower()
        status_score = 0 if status == 'shutdown' else 1
        candidates.append((status_score, created, model_id))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][2]


def generate_llm_summary(
    *,
    messages: list[dict[str, str]],
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> str:
    runtime = settings or runtime_settings
    api_base = str(runtime.LLM_API_BASE or '')
    request_url = _completion_url(api_base)
    model_name = str(runtime.LLM_ENDPOINT_ID or runtime.LLM_MODEL or '').strip()
    if not model_name:
        raise RuntimeError('LLM model identifier missing: set LLM_ENDPOINT_ID or LLM_MODEL')
    payload: dict[str, Any] = {
        'model': model_name,
        'messages': messages,
        'temperature': 0.2,
    }
    headers = {
        'Authorization': f'Bearer {runtime.LLM_API_KEY}',
        'Content-Type': 'application/json',
    }

    def _request_with_client(http_client: httpx.Client) -> httpx.Response:
        try:
            response = http_client.post(request_url, json=payload, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            error_code = _extract_error_code(exc.response)
            can_retry_with_alias = (
                not runtime.LLM_ENDPOINT_ID
                and error_code == 'InvalidEndpointOrModel.NotFound'
                and bool(runtime.LLM_MODEL)
            )
            if not can_retry_with_alias:
                raise

            resolved_model = _resolve_model_alias(
                base_url=api_base,
                headers=headers,
                alias=str(runtime.LLM_MODEL or ''),
                client=http_client,
            )
            if not resolved_model or resolved_model == payload['model']:
                raise

            payload['model'] = resolved_model
            retry_response = http_client.post(request_url, json=payload, headers=headers)
            try:
                retry_response.raise_for_status()
                return retry_response
            except httpx.HTTPStatusError as retry_exc:
                retry_error_code = _extract_error_code(retry_exc.response)
                retry_error_message = _extract_error_message(retry_exc.response).lower()
                can_retry_with_larger_size = (
                    retry_error_code == 'InvalidParameter'
                    and 'image size must be at least' in retry_error_message
                )
                if not can_retry_with_larger_size:
                    raise

                payload['size'] = '1920x1920'
                final_response = http_client.post(request_url, json=payload, headers=headers)
                final_response.raise_for_status()
                return final_response

    if client is None:
        with httpx.Client(timeout=runtime.LLM_TIMEOUT_SECONDS) as session:
            response = _request_with_client(session)
    else:
        response = _request_with_client(client)

    body: dict[str, Any] = response.json()
    choices = body.get('choices') if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError('LLM response does not contain choices')

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get('message') if isinstance(first_choice, dict) else {}
    content = message.get('content') if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError('LLM response does not contain message.content')
    return content.strip()


def generate_llm_image_asset(
    *,
    prompt: str,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    size: str = '1536x1024',
) -> dict[str, str]:
    runtime = settings or runtime_settings
    api_base = str(runtime.LLM_API_BASE or '')
    request_url = _images_url(api_base)
    image_model_configured = bool(str(runtime.LLM_IMAGE_ENDPOINT_ID or runtime.LLM_IMAGE_MODEL or '').strip())
    model_name = str(
        runtime.LLM_IMAGE_ENDPOINT_ID
        or runtime.LLM_IMAGE_MODEL
        or runtime.LLM_ENDPOINT_ID
        or runtime.LLM_MODEL
        or ''
    ).strip()
    if not model_name:
        raise RuntimeError('LLM image model identifier missing')

    payload: dict[str, Any] = {
        'model': model_name,
        'prompt': prompt,
        'size': size,
    }
    headers = {
        'Authorization': f'Bearer {runtime.LLM_API_KEY}',
        'Content-Type': 'application/json',
    }

    def _request_with_client(http_client: httpx.Client) -> httpx.Response:
        try:
            response = http_client.post(request_url, json=payload, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            error_code = _extract_error_code(exc.response)
            can_retry_with_alias = (
                image_model_configured
                and not runtime.LLM_IMAGE_ENDPOINT_ID
                and not runtime.LLM_ENDPOINT_ID
                and error_code == 'InvalidEndpointOrModel.NotFound'
                and bool(runtime.LLM_IMAGE_MODEL)
            )
            can_retry_with_discovered_image_model = (
                not image_model_configured
                and not runtime.LLM_IMAGE_ENDPOINT_ID
                and error_code in {'InvalidParameter', 'InvalidEndpointOrModel.NotFound'}
            )
            if not can_retry_with_alias and not can_retry_with_discovered_image_model:
                raise

            if can_retry_with_alias:
                resolved_model = _resolve_model_alias(
                    base_url=api_base,
                    headers=headers,
                    alias=str(runtime.LLM_IMAGE_MODEL or runtime.LLM_MODEL or ''),
                    client=http_client,
                )
            else:
                resolved_model = _resolve_latest_image_model(
                    base_url=api_base,
                    headers=headers,
                    client=http_client,
                )
            if not resolved_model or resolved_model == payload['model']:
                raise

            payload['model'] = resolved_model
            retry_response = http_client.post(request_url, json=payload, headers=headers)
            try:
                retry_response.raise_for_status()
                return retry_response
            except httpx.HTTPStatusError as retry_exc:
                retry_error_code = _extract_error_code(retry_exc.response)
                retry_error_message = _extract_error_message(retry_exc.response).lower()
                can_retry_with_larger_size = (
                    retry_error_code == 'InvalidParameter'
                    and 'image size must be at least' in retry_error_message
                )
                if not can_retry_with_larger_size:
                    raise

                payload['size'] = '1920x1920'
                final_response = http_client.post(request_url, json=payload, headers=headers)
                final_response.raise_for_status()
                return final_response

    if client is None:
        with httpx.Client(timeout=runtime.LLM_TIMEOUT_SECONDS) as session:
            response = _request_with_client(session)
    else:
        response = _request_with_client(client)

    body: dict[str, Any] = response.json()
    images = body.get('data') if isinstance(body, dict) else None
    if not isinstance(images, list) or not images:
        raise RuntimeError('LLM image response does not contain data')

    first = images[0] if isinstance(images[0], dict) else {}
    direct_url = str(first.get('url') or '').strip()
    if direct_url:
        return {
            'image_url': direct_url,
            'model': str(payload['model']),
        }

    b64_json = str(first.get('b64_json') or first.get('image_base64') or '').strip()
    if b64_json:
        return {
            'image_url': f'data:image/png;base64,{b64_json}',
            'model': str(payload['model']),
        }

    raise RuntimeError('LLM image response does not contain usable image payload')
