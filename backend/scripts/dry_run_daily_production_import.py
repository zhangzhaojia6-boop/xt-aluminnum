# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import Base, get_sessionmaker
import app.models  # noqa: F401  # register metadata for the in-memory dry-run database
from app.models.imports import ImportBatch, ImportRow
from app.models.production import ShiftProductionData
from app.services.daily_production_canonical_service import ParsedDailyProductionSheet, parse_daily_production_workbook
from app.services.daily_production_mapping_service import (
    build_daily_production_mapping_preview,
    serialize_daily_production_mapping_preview,
)
from app.services.real_master_data import seed_real_master_data


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必须为 YYYY-MM-DD") from exc


def _quality_status(parsed_sheets: list[ParsedDailyProductionSheet]) -> str:
    if not parsed_sheets:
        return "blocked"
    statuses = [str(sheet.mapped_data.get("quality_status") or "blocked") for sheet in parsed_sheets]
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    return "ready"


def _sum_mapped(parsed_sheets: list[ParsedDailyProductionSheet], field_name: str) -> float:
    total = sum(float(sheet.mapped_data.get(field_name) or 0.0) for sheet in parsed_sheets)
    return round(total, 3)


def _collect_issues(parsed_sheets: list[ParsedDailyProductionSheet]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for sheet in parsed_sheets:
        for issue in sheet.mapped_data.get("issues") or []:
            if isinstance(issue, dict):
                issues.append({"sheet_name": sheet.sheet_name, **issue})
    return issues


def _create_dry_run_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
    return SessionLocal()


def _store_transient_batch(
    db: Session,
    *,
    workbook_path: Path,
    parsed_sheets: list[ParsedDailyProductionSheet],
    quality_status: str,
    source_type: str = "dry_run",
    batch_no_prefix: str = "DRYRUN-DAILY",
    commit: bool = True,
) -> ImportBatch:
    batch = ImportBatch(
        batch_no=f"{batch_no_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        import_type="daily_production_report",
        source_type=source_type,
        file_name=workbook_path.name,
        file_size=workbook_path.stat().st_size,
        file_path=str(workbook_path),
        total_rows=len(parsed_sheets),
        success_rows=len([sheet for sheet in parsed_sheets if sheet.status == "success"]),
        failed_rows=len([sheet for sheet in parsed_sheets if sheet.status != "success"]),
        status="completed",
        quality_status=quality_status,
        parsed_successfully=bool(parsed_sheets) and quality_status != "blocked",
    )
    db.add(batch)
    db.flush()
    for row_number, sheet in enumerate(parsed_sheets, start=1):
        db.add(
            ImportRow(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=sheet.raw_data,
                mapped_data=sheet.mapped_data,
                status=sheet.status,
                error_msg=sheet.error_msg,
            )
        )
    db.flush()
    if commit:
        db.commit()
    return batch


def _blocking_issues(
    *,
    parsed_sheets: list[ParsedDailyProductionSheet],
    parse_issues: list[dict[str, Any]],
    mapping_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not parsed_sheets:
        issues.append({"code": "no_daily_production_summary_sheet", "message": "未找到每日产量综合报表。"})
    for issue in parse_issues:
        if issue.get("code") == "hard_block_kg_as_tons":
            issues.append(issue)
    if mapping_payload["unresolved_rows"] > 0:
        issues.append(
            {
                "code": "unresolved_daily_production_mapping",
                "message": f"仍有 {mapping_payload['unresolved_rows']} 行未匹配到车间主数据。",
            }
        )
    if mapping_payload["needs_equipment_mapping_rows"] > 0:
        issues.append(
            {
                "code": "missing_daily_production_equipment_mapping",
                "message": f"仍有 {mapping_payload['needs_equipment_mapping_rows']} 行缺少机列映射。",
            }
        )
    return issues


def _with_equipment_binding_summary(mapping_payload: dict[str, Any]) -> dict[str, Any]:
    rows = mapping_payload.get("rows") or []
    equipment_bound_rows = len([row for row in rows if row.get("equipment_id") is not None])
    workshop_only_rows = len(
        [
            row
            for row in rows
            if row.get("status") == "ready"
            and row.get("workshop_id") is not None
            and row.get("equipment_id") is None
        ]
    )
    return {
        **mapping_payload,
        "equipment_bound_rows": equipment_bound_rows,
        "workshop_only_rows": workshop_only_rows,
    }


def _build_output_payload(
    *,
    workbook_path: Path,
    report_date: date,
    parsed_sheets: list[ParsedDailyProductionSheet],
    parse_status: str,
    parse_issues: list[dict[str, Any]],
    mapping_payload: dict[str, Any],
    staging_write: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocking_issues = _blocking_issues(
        parsed_sheets=parsed_sheets,
        parse_issues=parse_issues,
        mapping_payload=mapping_payload,
    )

    payload = {
        "hard_gate_passed": not blocking_issues and parse_status != "blocked",
        "business_date": report_date.isoformat(),
        "source": {
            "file_name": workbook_path.name,
            "file_path": str(workbook_path),
        },
        "parse": {
            "sheet_count": len(parsed_sheets),
            "quality_status": parse_status,
            "issues": parse_issues,
        },
        "totals": {
            "source_unit": "t",
            "daily_input_tons": _sum_mapped(parsed_sheets, "daily_input_tons"),
            "daily_output_tons": _sum_mapped(parsed_sheets, "daily_output_tons"),
            "daily_scrap_tons": _sum_mapped(parsed_sheets, "daily_scrap_tons"),
            "month_to_date_input_tons": _sum_mapped(parsed_sheets, "month_to_date_input_tons"),
            "month_to_date_output_tons": _sum_mapped(parsed_sheets, "month_to_date_output_tons"),
            "month_to_date_scrap_tons": _sum_mapped(parsed_sheets, "month_to_date_scrap_tons"),
        },
        "mapping": mapping_payload,
        "blocking_issues": blocking_issues,
    }
    if staging_write is not None:
        payload["staging_write"] = staging_write
    return payload


def build_daily_production_dry_run(
    input_file: str | Path,
    *,
    report_date: date,
    year_hint: int | None = None,
) -> dict[str, Any]:
    workbook_path = Path(input_file)
    parsed_sheets = parse_daily_production_workbook(
        workbook_path,
        year_hint=year_hint or report_date.year,
        report_date_override=report_date,
    )
    parse_status = _quality_status(parsed_sheets)
    parse_issues = _collect_issues(parsed_sheets)

    db = _create_dry_run_session()
    try:
        seed_real_master_data(db)
        batch = _store_transient_batch(
            db,
            workbook_path=workbook_path,
            parsed_sheets=parsed_sheets,
            quality_status=parse_status,
        )
        preview = build_daily_production_mapping_preview(db, batch_id=batch.id)
        mapping_payload = _with_equipment_binding_summary(serialize_daily_production_mapping_preview(preview))
    finally:
        db.close()

    return _build_output_payload(
        workbook_path=workbook_path,
        report_date=report_date,
        parsed_sheets=parsed_sheets,
        parse_status=parse_status,
        parse_issues=parse_issues,
        mapping_payload=mapping_payload,
    )


def stage_daily_production_import(
    input_file: str | Path,
    *,
    report_date: date,
    db: Session,
    year_hint: int | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    workbook_path = Path(input_file)
    parsed_sheets = parse_daily_production_workbook(
        workbook_path,
        year_hint=year_hint or report_date.year,
        report_date_override=report_date,
    )
    parse_status = _quality_status(parsed_sheets)
    parse_issues = _collect_issues(parsed_sheets)
    fact_count_before = int(db.query(func.count(ShiftProductionData.id)).scalar() or 0)

    batch = _store_transient_batch(
        db,
        workbook_path=workbook_path,
        parsed_sheets=parsed_sheets,
        quality_status=parse_status,
        source_type="daily_production_report_locked",
        batch_no_prefix="IMP-DAILY-LOCKED",
        commit=False,
    )
    preview = build_daily_production_mapping_preview(db, batch_id=batch.id)
    mapping_payload = _with_equipment_binding_summary(serialize_daily_production_mapping_preview(preview))
    payload = _build_output_payload(
        workbook_path=workbook_path,
        report_date=report_date,
        parsed_sheets=parsed_sheets,
        parse_status=parse_status,
        parse_issues=parse_issues,
        mapping_payload=mapping_payload,
    )

    if not commit or not payload["hard_gate_passed"]:
        db.rollback()
        payload["staging_write"] = {
            "committed": False,
            "batch_id": None,
            "rows_written": 0,
            "production_fact_rows_written": 0,
        }
        return payload

    db.commit()
    fact_count_after = int(db.query(func.count(ShiftProductionData.id)).scalar() or 0)
    payload["staging_write"] = {
        "committed": True,
        "batch_id": batch.id,
        "rows_written": len(parsed_sheets),
        "production_fact_rows_written": fact_count_after - fact_count_before,
    }
    return payload


def _print_text(payload: dict[str, Any]) -> None:
    print(f"硬门禁：{'通过' if payload['hard_gate_passed'] else '未通过'}")
    print(f"报告日：{payload['business_date']}")
    print(f"来源文件：{payload['source']['file_path']}")
    print(f"解析状态：{payload['parse']['quality_status']}，工作表 {payload['parse']['sheet_count']} 个")
    print(
        "产量合计："
        f"投入 {payload['totals']['daily_input_tons']}t，"
        f"产出 {payload['totals']['daily_output_tons']}t，"
        f"废料 {payload['totals']['daily_scrap_tons']}t"
    )
    mapping = payload["mapping"]
    print(
        "映射结果："
        f"{mapping['ready_rows']}/{mapping['total_rows']} ready，"
        f"未匹配 {mapping['unresolved_rows']}，"
        f"缺机列 {mapping['needs_equipment_mapping_rows']}"
    )
    if payload["parse"]["issues"]:
        print("解析提示：")
        for issue in payload["parse"]["issues"]:
            print(f"- [{issue.get('code')}] {issue.get('message')}")
    if payload["blocking_issues"]:
        print("硬阻断：")
        for issue in payload["blocking_issues"]:
            print(f"- [{issue.get('code')}] {issue.get('message')}")
    if payload.get("staging_write"):
        staging = payload["staging_write"]
        print(
            "暂存写入："
            f"{'已提交' if staging['committed'] else '未提交'}，"
            f"批次 {staging.get('batch_id') or '--'}，"
            f"暂存行 {staging['rows_written']}，"
            f"正式事实行 {staging['production_fact_rows_written']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="每日产量真实报表只读 dry-run 对账")
    parser.add_argument("--input-file", required=True, help="每日产量 xls/xlsx 文件")
    parser.add_argument("--report-date", required=True, type=_parse_date, help="锁定报告日，格式 YYYY-MM-DD")
    parser.add_argument("--year-hint", type=int, default=None, help="缺省年份提示")
    parser.add_argument("--write-staging", action="store_true", help="写入导入暂存表；硬门禁失败会回滚")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="输出完整 JSON")
    args = parser.parse_args()

    if args.write_staging:
        SessionLocal = get_sessionmaker()
        with SessionLocal() as db:
            payload = stage_daily_production_import(
                args.input_file,
                report_date=args.report_date,
                year_hint=args.year_hint,
                db=db,
                commit=True,
            )
    else:
        payload = build_daily_production_dry_run(
            args.input_file,
            report_date=args.report_date,
            year_hint=args.year_hint,
        )
    if args.json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0 if payload["hard_gate_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
