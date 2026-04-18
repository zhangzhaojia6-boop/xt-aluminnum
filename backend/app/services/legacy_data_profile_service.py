from __future__ import annotations

from collections import Counter
from pathlib import Path
import importlib
from typing import Any

import pandas as pd

from app.services.contract_canonical_service import parse_contract_sheet
from app.services.yield_matrix_canonical_service import parse_yield_matrix_sheet


WORKBOOK_SUFFIXES = {".xlsx", ".xls"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def classify_legacy_file(file_name: str, sheet_names: list[str] | None = None) -> str:
    name = str(file_name or "").lower()
    sheets = [str(item) for item in (sheet_names or [])]

    if any(name.endswith(suffix) for suffix in IMAGE_SUFFIXES):
        return "shipping_image_capture"
    if "每日产量" in name:
        return "daily_production_report"
    if "成品率" in name:
        return "yield_rate_matrix"
    if "合同报表" in name:
        return "contract_report"
    if any("分类报表" in item for item in sheets):
        return "daily_production_report"
    if any("深加工" in item for item in sheets):
        return "daily_production_report"
    return "unknown"


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            return str(value)
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _normalize_value(value) for key, value in row.items()}


def _resolve_excel_engine(path: Path) -> tuple[str | None, str | None]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "openpyxl", None
    if suffix == ".xls":
        try:
            importlib.import_module("xlrd")
        except ModuleNotFoundError:
            return None, "xlrd_missing"
        return "xlrd", None
    return None, "unsupported_suffix"


def profile_historical_path(path: str | Path, *, max_sheets: int = 3, max_rows: int = 3) -> dict[str, Any]:
    target = Path(path)
    suffix = target.suffix.lower()
    item: dict[str, Any] = {
        "file_name": target.name,
        "path": str(target),
        "suffix": suffix,
        "kind": classify_legacy_file(target.name),
    }

    if suffix in IMAGE_SUFFIXES:
        item["status"] = "profiled"
        item["notes"] = ["image-based legacy shipping/inventory report; requires OCR or manual structuring"]
        return item

    if suffix not in WORKBOOK_SUFFIXES:
        item["status"] = "skipped"
        item["issues"] = [{"code": "unsupported_suffix", "message": f"Unsupported suffix: {suffix}"}]
        return item

    engine, issue_code = _resolve_excel_engine(target)
    if issue_code:
        item["status"] = "blocked"
        item["issues"] = [
            {
                "code": issue_code,
                "message": "Current runtime cannot read legacy .xls directly; convert to .xlsx or use host Python with xlrd.",
            }
        ]
        return item

    workbook = pd.ExcelFile(target, engine=engine)
    item["sheet_names"] = list(workbook.sheet_names)
    item["kind"] = classify_legacy_file(target.name, workbook.sheet_names)
    item["sheets"] = []
    for sheet_name in workbook.sheet_names[: max(1, max_sheets)]:
        df = pd.read_excel(target, sheet_name=sheet_name, nrows=max_rows, engine=engine)
        sheet_payload = {
            "sheet_name": str(sheet_name),
            "columns": [str(column) for column in df.columns.tolist()],
            "preview_rows": [_normalize_row(row) for row in df.to_dict(orient="records")[:max_rows]],
        }
        if item["kind"] == "contract_report":
            raw_df = pd.read_excel(target, sheet_name=sheet_name, header=None, engine=engine)
            parsed = parse_contract_sheet(str(sheet_name), raw_df, year_hint=None)
            sheet_payload["contract_preview"] = parsed.mapped_data
        if item["kind"] == "yield_rate_matrix":
            raw_df = pd.read_excel(target, sheet_name=sheet_name, header=None, engine=engine)
            parsed = parse_yield_matrix_sheet(str(sheet_name), raw_df, year_hint=None)
            sheet_payload["yield_matrix_preview"] = parsed.mapped_data
        item["sheets"].append(sheet_payload)
    item["status"] = "profiled"
    return item


def profile_historical_directory(path: str | Path, *, max_sheets: int = 3, max_rows: int = 3) -> dict[str, Any]:
    base = Path(path)
    items = [
        profile_historical_path(file_path, max_sheets=max_sheets, max_rows=max_rows)
        for file_path in sorted(base.iterdir())
        if file_path.is_file()
    ]
    kind_counter = Counter(item.get("kind", "unknown") for item in items)
    blocked = [item for item in items if item.get("status") == "blocked"]
    return {
        "base_path": str(base),
        "total_files": len(items),
        "kind_counts": dict(kind_counter),
        "blocked_files": len(blocked),
        "items": items,
    }
