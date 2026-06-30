from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.agent_sop_bootstrap_service import build_zzj_agent_sop_plan, ensure_zzj_agent_sop


def main() -> int:
    parser = argparse.ArgumentParser(description='配置张兆嘉六个 Agent 的 SOP 工作流')
    parser.add_argument('--apply', action='store_true', help='写入数据库；默认只预览')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({**build_zzj_agent_sop_plan(), 'applied': False}, ensure_ascii=False, indent=2))
        return 0
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        outcome = ensure_zzj_agent_sop(db, apply=True)
        db.commit()
    print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
