from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, settings as runtime_settings


def _completion_url(base_url: str) -> str:
    normalized = str(base_url or '').rstrip('/')
    if normalized.endswith('/chat/completions'):
        return normalized
    return f'{normalized}/chat/completions'


def generate_llm_summary(
    *,
    messages: list[dict[str, str]],
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> str:
    runtime = settings or runtime_settings
    request_url = _completion_url(str(runtime.LLM_API_BASE or ''))
    payload = {
        'model': runtime.LLM_MODEL,
        'messages': messages,
        'temperature': 0.2,
    }
    headers = {
        'Authorization': f'Bearer {runtime.LLM_API_KEY}',
        'Content-Type': 'application/json',
    }

    if client is None:
        with httpx.Client(timeout=runtime.LLM_TIMEOUT_SECONDS) as session:
            response = session.post(request_url, json=payload, headers=headers)
    else:
        response = client.post(request_url, json=payload, headers=headers)

    response.raise_for_status()
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
