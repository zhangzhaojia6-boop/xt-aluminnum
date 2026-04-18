"""Profile legacy workshop statistics files before formal system migration.

This script is intentionally read-only. It helps convert old manual-statistics
assets into a structured inventory so the system can optimize around real
business evidence instead of mock assumptions.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT_DIR / "backend" / "app" / "services" / "legacy_data_profile_service.py"
SPEC = importlib.util.spec_from_file_location("legacy_data_profile_service", SERVICE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
profile_historical_directory = MODULE.profile_historical_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile legacy workshop statistics files")
    parser.add_argument("--input-dir", required=True, help="Directory containing historical xls/xlsx/png files")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    payload = profile_historical_directory(args.input_dir)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
