from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings


def _health_payload() -> dict[str, object]:
    if not settings.DINGTALK_STREAM_ENABLED:
        return {'status': 'disabled', 'stream_enabled': False}
    return {'status': 'not_implemented', 'stream_enabled': True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--health', action='store_true')
    args = parser.parse_args()

    if args.health:
        print(json.dumps(_health_payload(), ensure_ascii=False))
        return 0 if not settings.DINGTALK_STREAM_ENABLED else 1

    parser.error('Stream runtime is not implemented yet')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
