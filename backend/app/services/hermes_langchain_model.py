from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class FactoryBrainModelUnavailable(RuntimeError):
    user_message: str
    cause: str


def invoke_factory_brain_model(
    *,
    messages: list[dict[str, str]],
    api_base: str,
    api_key: str,
    model: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    payload = {'model': model, 'messages': messages, 'temperature': 0.2}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    url = f'{api_base.rstrip("/")}/chat/completions'
    http_client = client or httpx.Client(timeout=20)
    try:
        response = http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise FactoryBrainModelUnavailable(
                user_message='模型服务暂不可用，Hermes 已降级为只读数据查询模式。',
                cause='model_auth_401',
            ) from exc
        raise
    return response.json()
