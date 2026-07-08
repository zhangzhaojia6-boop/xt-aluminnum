from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings, settings


def build_health_payload(runtime_settings: Settings = settings) -> dict[str, object]:
    if not runtime_settings.DINGTALK_STREAM_ENABLED:
        return {'status': 'disabled', 'stream_enabled': False}
    return {'status': 'not_implemented', 'stream_enabled': True}


def main(
    argv: list[str] | None = None,
    runtime_settings: Settings = settings,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    parser = argparse.ArgumentParser()
    parser.add_argument('--health', action='store_true')
    args = parser.parse_args(argv)

    if args.health:
        payload = build_health_payload(runtime_settings=runtime_settings)
        print(json.dumps(payload, ensure_ascii=False), file=output)
        return 0 if payload['status'] == 'disabled' else 1

    parser.print_usage(error_output)
    print(f'{parser.prog}: error: Stream runtime is not implemented yet', file=error_output)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
