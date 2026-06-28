from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.hermes_datahub_diet_audit_service import check_candidate_delete_paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check datahub candidate deletes")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    normalized_paths = [path.replace("\\", "/") for path in args.paths]
    result = check_candidate_delete_paths(ROOT, normalized_paths)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["items"]:
            print(f"{item['status']} {item['path']} {item['reason']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
