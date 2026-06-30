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
from app.services.rag_bootstrap_service import bootstrap_rag_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description='导入稳定 RAG 知识库资料')
    parser.add_argument('--reference-root', default='D:/输出skill')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(args.reference_root)
    if not root.exists():
        print(
            json.dumps(
                {'applied': False, 'error': 'reference_root_not_found', 'reference_root': str(root)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        outcome = bootstrap_rag_knowledge(db, reference_root=root, apply=args.apply)
        if args.apply:
            db.commit()
    print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
