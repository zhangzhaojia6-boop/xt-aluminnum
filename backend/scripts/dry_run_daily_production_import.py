# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
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
from app.domain.daily_report_field_contract import (
    DAILY_REPORT_FIELD_CONTRACTS,
    DAILY_REPORT_FIELD_CONTRACT_VERSION,
)
from app.models.imports import ImportBatch, ImportedDailyMetricFact, ImportRow
from app.models.production import ShiftProductionData
from app.models.shift import ShiftConfig
from app.services.daily_production_canonical_service import (
    HARD_BLOCK_DAILY_OUTPUT_TONS,
    ParsedDailyProductionSheet,
    daily_production_lineage_is_valid,
    parse_daily_production_workbook,
)
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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_value(total: float, seen: bool) -> float | None:
    return round(total, 3) if seen else None


def _active_shift_duplicate(
    db: Session,
    *,
    business_date: date,
    shift_config_id: int,
    workshop_id: int,
    equipment_id: int | None,
) -> ShiftProductionData | None:
    query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == business_date,
        ShiftProductionData.shift_config_id == shift_config_id,
        ShiftProductionData.workshop_id == workshop_id,
        ShiftProductionData.data_status != "voided",
    )
    if equipment_id is None:
        query = query.filter(ShiftProductionData.equipment_id.is_(None))
    else:
        query = query.filter(ShiftProductionData.equipment_id == equipment_id)
    return query.order_by(ShiftProductionData.version_no.desc(), ShiftProductionData.id.desc()).first()


def _batch_parse_issues(db: Session, *, batch_id: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    rows = db.query(ImportRow).filter(ImportRow.batch_id == batch_id).order_by(ImportRow.row_number.asc()).all()
    for row in rows:
        mapped_data = row.mapped_data if isinstance(row.mapped_data, dict) else {}
        for issue in mapped_data.get("issues") or []:
            if isinstance(issue, dict):
                issues.append({"row_number": row.row_number, **issue})
    return issues


def _daily_fact_buckets(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[date, int, int | None], dict[str, Any]] = {}
    for row in mapping_rows:
        if row.get("status") != "ready":
            continue
        business_date_raw = row.get("business_date")
        workshop_id = row.get("workshop_id")
        if not business_date_raw or workshop_id is None:
            continue
        business_date = date.fromisoformat(str(business_date_raw))
        equipment_id = row.get("equipment_id")
        key = (business_date, int(workshop_id), int(equipment_id) if equipment_id is not None else None)
        bucket = buckets.setdefault(
            key,
            {
                "business_date": business_date,
                "workshop_id": int(workshop_id),
                "equipment_id": int(equipment_id) if equipment_id is not None else None,
                "input_total": 0.0,
                "input_seen": False,
                "output_total": 0.0,
                "output_seen": False,
                "scrap_total": 0.0,
                "scrap_seen": False,
                "source_labels": [],
            },
        )
        input_weight = _to_float(row.get("daily_input_tons"))
        output_weight = _to_float(row.get("daily_output_tons"))
        scrap_weight = _to_float(row.get("daily_scrap_tons"))
        if input_weight is not None:
            bucket["input_total"] += input_weight
            bucket["input_seen"] = True
        if output_weight is not None:
            bucket["output_total"] += output_weight
            bucket["output_seen"] = True
        if scrap_weight is not None:
            bucket["scrap_total"] += scrap_weight
            bucket["scrap_seen"] = True
        label = "/".join(
            item
            for item in (str(row.get("workshop_label") or "").strip(), str(row.get("project_label") or "").strip())
            if item
        )
        if label:
            bucket["source_labels"].append(label)
    return [
        bucket
        for bucket in buckets.values()
        if any(bucket[f"{metric}_seen"] for metric in ("input", "output", "scrap"))
    ]


def _valid_source_anchors(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(
        isinstance(anchor, dict)
        and str(anchor.get("sheet_name") or "").strip()
        and isinstance(anchor.get("row_index"), int)
        and anchor["row_index"] >= 0
        and isinstance(anchor.get("column_index"), int)
        and anchor["column_index"] >= 0
        for anchor in value
    )


def _valid_report_metric_value(field_name: str, unit: str, value: float) -> bool:
    if value < 0:
        return False
    if unit == "道" and not math.isclose(value, round(value), rel_tol=0.0, abs_tol=0.000001):
        return False
    if unit == "吨":
        max_tonnage = HARD_BLOCK_DAILY_OUTPUT_TONS * (31 if field_name.endswith("_month") else 1)
        if value > max_tonnage:
            return False
    return True


def _batch_report_metrics(
    db: Session,
    *,
    batch_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metrics: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen_fields: set[tuple[date, str]] = set()
    rows = db.query(ImportRow).filter(ImportRow.batch_id == batch_id).order_by(ImportRow.row_number.asc()).all()
    for row in rows:
        if row.status != "success":
            continue
        mapped = row.mapped_data if isinstance(row.mapped_data, dict) else {}
        if not daily_production_lineage_is_valid(mapped):
            issues.append(
                {
                    "code": "invalid_daily_production_lineage",
                    "message": f"暂存行 {row.row_number} 的谱系哈希无效。",
                    "import_row_id": row.id,
                }
            )
            continue
        raw_metrics = mapped.get("report_metrics") or []
        if not isinstance(raw_metrics, list):
            issues.append(
                {
                    "code": "invalid_daily_report_metrics",
                    "message": f"暂存行 {row.row_number} 的日报指标结构无效。",
                    "import_row_id": row.id,
                }
            )
            continue
        try:
            business_date = date.fromisoformat(str(mapped.get("business_date") or ""))
        except ValueError:
            if raw_metrics:
                issues.append(
                    {
                        "code": "invalid_daily_report_metric_date",
                        "message": f"暂存行 {row.row_number} 的日报指标缺少有效业务日。",
                        "import_row_id": row.id,
                    }
                )
            continue
        for metric in raw_metrics:
            field_name = str(metric.get("field_name") or "").strip() if isinstance(metric, dict) else ""
            contract = DAILY_REPORT_FIELD_CONTRACTS.get(field_name)
            value = _to_float(metric.get("value")) if isinstance(metric, dict) else None
            unit = str(metric.get("unit") or "").strip() if isinstance(metric, dict) else ""
            anchors = metric.get("source_anchors") if isinstance(metric, dict) else None
            field_key = (business_date, field_name)
            if (
                contract is None
                or value is None
                or not math.isfinite(value)
                or not _valid_report_metric_value(field_name, unit, value)
                or unit != contract.unit
                or not _valid_source_anchors(anchors)
                or field_key in seen_fields
            ):
                issues.append(
                    {
                        "code": "invalid_daily_report_metric",
                        "message": f"暂存行 {row.row_number} 的日报指标 {field_name or '--'} 未通过字段契约。",
                        "import_row_id": row.id,
                        "field_name": field_name or None,
                    }
                )
                continue
            seen_fields.add(field_key)
            metrics.append(
                {
                    "business_date": business_date,
                    "field_name": field_name,
                    "metric_value": value,
                    "unit": unit,
                    "import_row": row,
                    "source_anchors": anchors,
                    "lineage_hash": str(mapped["lineage_hash"]),
                }
            )
    return metrics, issues


def _active_metric_duplicate(
    db: Session,
    *,
    business_date: date,
    field_name: str,
) -> ImportedDailyMetricFact | None:
    return (
        db.query(ImportedDailyMetricFact)
        .filter(
            ImportedDailyMetricFact.business_date == business_date,
            ImportedDailyMetricFact.field_name == field_name,
            ImportedDailyMetricFact.source_kind == "daily_production_report",
            ImportedDailyMetricFact.data_status == "confirmed",
        )
        .order_by(ImportedDailyMetricFact.version_no.desc(), ImportedDailyMetricFact.id.desc())
        .first()
    )


def promote_daily_production_batch(
    db: Session,
    *,
    batch_id: int,
    shift_code: str = "A",
    duplicate_strategy: str = "reject",
    commit: bool = False,
) -> dict[str, Any]:
    duplicate_strategy = str(duplicate_strategy or "reject").strip().lower()
    if duplicate_strategy not in {"reject", "supersede"}:
        raise ValueError("duplicate_strategy must be reject or supersede")

    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.import_type != "daily_production_report":
        raise ValueError(f"daily_production_report batch not found: {batch_id}")
    shift = db.query(ShiftConfig).filter(ShiftConfig.code == shift_code, ShiftConfig.is_active.is_(True)).first()
    if shift is None:
        raise ValueError(f"shift not found: {shift_code}")

    preview = build_daily_production_mapping_preview(db, batch_id=batch.id)
    mapping_payload = _with_equipment_binding_summary(serialize_daily_production_mapping_preview(preview))
    parse_issues = _batch_parse_issues(db, batch_id=batch.id)
    report_metrics, report_metric_issues = _batch_report_metrics(db, batch_id=batch.id)
    blocking_issues: list[dict[str, Any]] = []
    if batch.source_type != "daily_production_report_locked":
        blocking_issues.append(
            {
                "code": "unlocked_daily_production_batch",
                "message": "每日产量批次未锁定业务日，禁止提升为正式事实。",
            }
        )
    if batch.quality_status == "blocked":
        blocking_issues.append({"code": "blocked_daily_production_batch", "message": "每日产量暂存批次处于 blocked 状态。"})
    blocking_issues.extend(issue for issue in parse_issues if issue.get("code") == "hard_block_kg_as_tons")
    blocking_issues.extend(report_metric_issues)
    if mapping_payload["unresolved_rows"] > 0:
        blocking_issues.append({"code": "unresolved_daily_production_mapping", "message": f"仍有 {mapping_payload['unresolved_rows']} 行未匹配。"})
    if mapping_payload["needs_equipment_mapping_rows"] > 0:
        blocking_issues.append({"code": "missing_daily_production_equipment_mapping", "message": f"仍有 {mapping_payload['needs_equipment_mapping_rows']} 行缺少机列。"})

    buckets = _daily_fact_buckets(mapping_payload.get("rows") or [])
    duplicate_rows: list[dict[str, Any]] = []
    for bucket in buckets:
        existing = _active_shift_duplicate(
            db,
            business_date=bucket["business_date"],
            shift_config_id=shift.id,
            workshop_id=bucket["workshop_id"],
            equipment_id=bucket["equipment_id"],
        )
        if existing is not None and duplicate_strategy == "reject":
            duplicate_rows.append(
                {
                    "existing_id": existing.id,
                    "business_date": bucket["business_date"].isoformat(),
                    "workshop_id": bucket["workshop_id"],
                    "equipment_id": bucket["equipment_id"],
                }
            )
    if duplicate_rows:
        blocking_issues.append(
            {
                "code": "duplicate_daily_production_fact",
                "message": f"已有 {len(duplicate_rows)} 条同日/班次/车间/机列正式产量，默认拒绝覆盖。",
                "duplicates": duplicate_rows,
            }
        )

    duplicate_metric_rows: list[dict[str, Any]] = []
    if duplicate_strategy == "reject":
        for metric in report_metrics:
            existing = _active_metric_duplicate(
                db,
                business_date=metric["business_date"],
                field_name=metric["field_name"],
            )
            if existing is not None:
                duplicate_metric_rows.append(
                    {
                        "existing_id": existing.id,
                        "business_date": metric["business_date"].isoformat(),
                        "field_name": metric["field_name"],
                    }
                )
    if duplicate_metric_rows:
        blocking_issues.append(
            {
                "code": "duplicate_daily_report_metric_fact",
                "message": f"已有 {len(duplicate_metric_rows)} 条同日正式日报指标，默认拒绝覆盖。",
                "duplicates": duplicate_metric_rows,
            }
        )

    if blocking_issues:
        db.rollback()
        return {
            "committed": False,
            "batch_id": batch.id,
            "shift_code": shift.code,
            "duplicate_strategy": duplicate_strategy,
            "fact_rows_written": 0,
            "metric_fact_rows_written": 0,
            "total_output_tons": 0.0,
            "projected_metric_fact_rows": len(report_metrics),
            "blocking_issues": blocking_issues,
        }

    written = 0
    metric_written = 0
    total_output = 0.0
    now = datetime.now(timezone.utc)
    for bucket in buckets:
        existing = _active_shift_duplicate(
            db,
            business_date=bucket["business_date"],
            shift_config_id=shift.id,
            workshop_id=bucket["workshop_id"],
            equipment_id=bucket["equipment_id"],
        )
        next_version = 1
        if existing is not None:
            next_version = (existing.version_no or 1) + 1
            existing.data_status = "voided"
            existing.voided_at = now
            existing.voided_reason = f"superseded by daily production batch {batch.batch_no}"

        output_weight = _metric_value(bucket["output_total"], bucket["output_seen"])
        entity = ShiftProductionData(
            business_date=bucket["business_date"],
            shift_config_id=shift.id,
            workshop_id=bucket["workshop_id"],
            equipment_id=bucket["equipment_id"],
            input_weight=_metric_value(bucket["input_total"], bucket["input_seen"]),
            output_weight=output_weight,
            qualified_weight=output_weight,
            scrap_weight=_metric_value(bucket["scrap_total"], bucket["scrap_seen"]),
            data_source="daily_production_report",
            import_batch_id=batch.id,
            data_status="confirmed",
            version_no=next_version,
            confirmed_at=now,
            notes=f"daily production report batch {batch.batch_no}; source rows: {', '.join(bucket['source_labels'])}",
        )
        db.add(entity)
        try:
            db.flush()
        except Exception:
            db.rollback()
            raise
        if existing is not None:
            existing.superseded_by_id = entity.id
        written += 1
        total_output += float(output_weight or 0.0)

    for metric in report_metrics:
        existing = _active_metric_duplicate(
            db,
            business_date=metric["business_date"],
            field_name=metric["field_name"],
        )
        next_version = 1
        if existing is not None:
            next_version = (existing.version_no or 1) + 1
            existing.data_status = "voided"
            existing.voided_at = now
            existing.voided_reason = f"superseded by daily production batch {batch.batch_no}"
            try:
                db.flush()
            except Exception:
                db.rollback()
                raise
        entity = ImportedDailyMetricFact(
            business_date=metric["business_date"],
            field_name=metric["field_name"],
            metric_value=metric["metric_value"],
            unit=metric["unit"],
            source_kind="daily_production_report",
            import_batch_id=batch.id,
            import_row_id=metric["import_row"].id,
            source_anchors=metric["source_anchors"],
            lineage_hash=metric["lineage_hash"],
            metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
            data_status="confirmed",
            version_no=next_version,
            confirmed_at=now,
        )
        db.add(entity)
        try:
            db.flush()
        except Exception:
            db.rollback()
            raise
        if existing is not None:
            existing.superseded_by_id = entity.id
        metric_written += 1

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    else:
        db.rollback()
    return {
        "committed": bool(commit),
        "batch_id": batch.id,
        "shift_code": shift.code,
        "duplicate_strategy": duplicate_strategy,
        "fact_rows_written": written if commit else 0,
        "metric_fact_rows_written": metric_written if commit else 0,
        "total_output_tons": round(total_output, 3) if commit else 0.0,
        "projected_fact_rows": written,
        "projected_metric_fact_rows": metric_written,
        "projected_output_tons": round(total_output, 3),
        "blocking_issues": [],
    }


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


def _print_promotion_text(payload: dict[str, Any]) -> None:
    print(f"正式事实写入：{'已提交' if payload['committed'] else '未提交'}")
    print(f"批次：{payload['batch_id']}，班次：{payload['shift_code']}，重复策略：{payload['duplicate_strategy']}")
    print(f"写入事实行：{payload['fact_rows_written']}，产量合计：{payload['total_output_tons']}t")
    if not payload["committed"] and "projected_fact_rows" in payload:
        print(f"预计写入：{payload['projected_fact_rows']} 行，预计产量：{payload['projected_output_tons']}t")
    if payload.get("blocking_issues"):
        print("硬阻断：")
        for issue in payload["blocking_issues"]:
            print(f"- [{issue.get('code')}] {issue.get('message')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="每日产量真实报表只读 dry-run 对账")
    parser.add_argument("--input-file", help="每日产量 xls/xlsx 文件")
    parser.add_argument("--report-date", type=_parse_date, help="锁定报告日，格式 YYYY-MM-DD")
    parser.add_argument("--year-hint", type=int, default=None, help="缺省年份提示")
    parser.add_argument("--write-staging", action="store_true", help="写入导入暂存表；硬门禁失败会回滚")
    parser.add_argument("--promote-facts", action="store_true", help="将已通过门禁的暂存批次写入正式产量事实表")
    parser.add_argument("--batch-id", type=int, default=None, help="--promote-facts 使用的 ImportBatch id")
    parser.add_argument("--shift-code", default="A", help="--promote-facts 使用的班次编码，默认 A")
    parser.add_argument("--duplicate-strategy", choices=["reject", "supersede"], default="reject")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="输出完整 JSON")
    args = parser.parse_args()

    if args.promote_facts:
        if args.batch_id is None:
            parser.error("--promote-facts requires --batch-id")
        SessionLocal = get_sessionmaker()
        with SessionLocal() as db:
            payload = promote_daily_production_batch(
                db,
                batch_id=args.batch_id,
                shift_code=args.shift_code,
                duplicate_strategy=args.duplicate_strategy,
                commit=True,
            )
        if args.json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            _print_promotion_text(payload)
        return 0 if payload["committed"] else 1

    if not args.input_file or args.report_date is None:
        parser.error("--input-file and --report-date are required unless --promote-facts is used")

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
