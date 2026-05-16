from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.llm import LlmTextResponse, generate_llm_summary_with_usage
from app.config import Settings, settings


def _is_blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _missing_llm_env(runtime: Settings) -> list[str]:
    missing: list[str] = []
    if not runtime.LLM_ENABLED:
        missing.append('LLM_ENABLED')
    if _is_blank(runtime.LLM_API_BASE):
        missing.append('LLM_API_BASE')
    if _is_blank(runtime.LLM_API_KEY):
        missing.append('LLM_API_KEY')
    if _is_blank(runtime.LLM_MODEL) and _is_blank(runtime.LLM_ENDPOINT_ID):
        missing.append('LLM_MODEL_OR_ENDPOINT_ID')
    return missing


def inspect_llm_live(
    *,
    runtime_settings: Settings | None = None,
    summary_func: Callable[..., LlmTextResponse] = generate_llm_summary_with_usage,
    prompt: str = 'Reply only with DATA_HUB_LLM_OK.',
) -> dict[str, Any]:
    runtime = runtime_settings or settings
    missing_env = _missing_llm_env(runtime)
    if missing_env:
        return {
            'ok': False,
            'configured': False,
            'missing_env': missing_env,
            'response_received': False,
        }

    try:
        response = summary_func(
            messages=[
                {'role': 'system', 'content': 'You are a connectivity probe. Keep the response short.'},
                {'role': 'user', 'content': prompt},
            ],
            settings=runtime,
            max_tokens=64,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            'ok': False,
            'configured': True,
            'missing_env': [],
            'response_received': False,
            'error': exc.__class__.__name__,
        }

    content = str(response.content or '')
    return {
        'ok': bool(content.strip()),
        'configured': True,
        'missing_env': [],
        'response_received': bool(content.strip()),
        'content_length': len(content),
        'content_preview': content[:120],
        'usage': {
            'input_tokens': int(response.input_tokens or 0),
            'output_tokens': int(response.output_tokens or 0),
            'total_tokens': int(response.total_tokens or 0),
        },
    }


def main(
    argv: list[str] | None = None,
    *,
    runtime_settings: Settings | None = None,
    summary_func: Callable[..., LlmTextResponse] = generate_llm_summary_with_usage,
) -> int:
    parser = argparse.ArgumentParser(description='Check live LLM connectivity without printing API keys.')
    parser.add_argument('--json', action='store_true', help='Print JSON output.')
    parser.add_argument('--prompt', default='Reply only with DATA_HUB_LLM_OK.', help='Short prompt to send.')
    args = parser.parse_args(argv)

    payload = inspect_llm_live(runtime_settings=runtime_settings, summary_func=summary_func, prompt=args.prompt)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload['ok']:
        print('llm_live=ok')
        print(f"content_length={payload['content_length']}")
        print(f"total_tokens={payload['usage']['total_tokens']}")
    else:
        print('llm_live=failed')
        if payload.get('missing_env'):
            print(f"missing_env={','.join(payload['missing_env'])}")
        if payload.get('error'):
            print(f"error={payload['error']}")

    if payload['ok']:
        return 0
    return 2 if not payload['configured'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
