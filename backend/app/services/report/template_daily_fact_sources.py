from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, func, inspect, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.business_time import production_business_window
from app.models.master import Workshop
from app.models.mes import (
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMaterialRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
)
from app.models.production import OverhaulDaily, RecoveryDaily, WorkOrderEntry
from app.models.quality import QualityYieldDaily
from app.models.reports import DailyReport, DailyReportHistoryRecord
from app.services.report import daily_overview_builder
from app.services.report._utils import _to_float
from app.services.report.mes_workshop_mapping import resolve_mes_process_workshop_bucket
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


SUBMITTED_STATUSES = ("submitted", "verified", "approved")
DATAHUB_TEMPLATE_REPORT_KEY = "template_daily_report"

SOURCE_PRIORITY = {
    "owner_daily": 100,
    "manual_workbook": 95,
    "wms_direct": 90,
    "mes_verified": 85,
    "manual_mobile_coil": 80,
    "owner_daily_month_sum": 78,
    "quality_yield_daily": 76,
    "recovery_daily": 76,
    "overhaul_daily": 76,
    "mes_stock_header_records": 72,
    "mes_stock_records": 72,
    "mes_stock_records_missing": 72,
    "finished_inbound_output": 72,
    "datahub_final_daily_report": 88,
    "previous_final_report": 70,
    "computed": 65,
    "owner_or_energy_summary": 62,
    "energy_cost": 62,
    "contract_projection": 60,
    "yield_projection": 60,
    "mes_packaging_output": 45,
    "mes_delivery_records": 45,
    "mes_wip_distribution": 40,
    "mes_daily_wip_snapshot": 40,
    "mes_coil_snapshot_business_date": 40,
    "mes_wip_total_snapshot": 40,
    "mes_material_records": 35,
    "mes_workshop_process_records": 35,
    "runtime_target_date": 30,
    "mes_evidence": 20,
}

MANUAL_OUTPUT_FIELDS = {
    "hot_roll_daily",
    "hot_roll_month",
    "foundry_daily",
    "foundry_month",
    "cast_2_daily",
    "cast_2_month",
    "cast_3_daily",
    "cast_3_month",
}

MANUAL_OUTPUT_WORKSHOPS = {
    "hot_roll_daily": ("热轧",),
    "foundry_daily": ("铸锭", "熔铸", "熔炼"),
    "cast_2_daily": ("铸二", "铸轧二"),
    "cast_3_daily": ("铸三", "铸轧三"),
}

MES_MATERIAL_OUTPUT_WORKSHOPS = {
    "hot_roll_daily": ("热轧车间", "热轧"),
    "cast_2_daily": ("铸二车间", "铸二", "铸轧二", "铸轧二车间", "铸轧2"),
    "cast_3_daily": ("铸三车间", "铸三", "铸轧三", "铸轧三车间", "铸轧3"),
}

MES_REPORT_PROCESS_BUCKETS = {
    "hot_roll_daily": ("热轧",),
    "foundry_daily": ("铸锭",),
    "cast_2_daily": ("铸二",),
    "cast_3_daily": ("铸三",),
    "cold_1650_daily": ("冷轧1650",),
    "cold_1850_daily": ("冷轧1850",),
    "cold_2050_daily": ("冷轧2050",),
    "online_anneal_daily": ("新厂在线", "园区在线"),
    "straightening_daily": ("拉矫",),
    "finishing_daily": ("精整",),
    "shearing_daily": ("园区剪切",),
    "coating_daily": ("彩涂",),
}
BILLET_MATERIAL_FIELDS = set(MES_MATERIAL_OUTPUT_WORKSHOPS)
BILLET_BUSINESS_DAY_START = time(10, 0)
BILLET_MATERIAL_INCLUDED_STATUS_NAMES = ("已使用", "未使用")

MONTHLY_FIELD_BY_DAILY_FIELD = {
    "hot_roll_daily": "hot_roll_month",
    "foundry_daily": "foundry_month",
    "cast_2_daily": "cast_2_month",
    "cast_3_daily": "cast_3_month",
    "cold_1650_daily": "cold_1650_month",
    "cold_1850_daily": "cold_1850_month",
    "cold_2050_daily": "cold_2050_month",
    "online_anneal_daily": "online_anneal_month",
    "straightening_daily": "straightening_month",
    "finishing_daily": "finishing_month",
    "shearing_daily": "shearing_month",
    "coating_daily": "coating_month",
}

OWNER_FIELD_ALIASES = {
    "daily_yield_rate": ("daily_yield_rate", "plant_wide_yield_rate"),
    "hot_roll_furnace_gas_m3": ("hot_roll_furnace_gas_m3", "heating_furnace_gas_m3"),
    "hot_roll_boiler_gas_m3": ("hot_roll_boiler_gas_m3", "boiler_gas_m3"),
    "cold_roll_input_daily": ("cold_roll_input_daily", "daily_input_weight"),
    "recovery_daily": ("recovery_daily", "recovery_weight", "recovery_output_tons"),
}

OWNER_MONTH_SUM_ALIASES = {
    "recovery_month": ("recovery_month", "recovery_weight", "recovery_daily", "recovery_output_tons"),
}

QUALITY_FACTORY_CODES = {"FACTORY", "COMPANY", "ALL", "M", "全厂", "公司"}
QUALITY_HOT_ROLL_CODES = {"HOT_ROLL", "HOTROLL", "HR", "RZ", "热轧"}
QUALITY_CAST_ROLL_CODES = {"CAST_ROLL", "CASTROLL", "ZR", "铸轧"}
QUALITY_PLATE_COIL_CODES = {"PLATE_COIL", "PLATECOIL", "PB", "PBC", "普板", "普板卷"}

WIP_BREAKDOWN_FIELDS = (
    "wip_1650_2050_cold",
    "wip_1850_cold",
    "wip_milling",
    "wip_new_north",
    "wip_new_south",
    "wip_park_anneal",
    "wip_straightening",
    "wip_finishing",
    "wip_park_finishing",
    "wip_hot_plate_shearing",
    "wip_coating",
)


@dataclass
class TemplateDailyFacts:
    target_date: date
    wip_date: date | None = None
    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "wip_date": self.wip_date.isoformat() if self.wip_date else None,
            "values": self.values,
            "sources": self.sources,
            "missing_fields": self.missing_fields,
            "conflicts": self.conflicts,
        }


def _source(source_type: str, **extra: Any) -> dict[str, Any]:
    return {"source_type": source_type, **extra}


def _source_priority(source_type: str | None) -> int:
    if not source_type:
        return 0
    if source_type in SOURCE_PRIORITY:
        return SOURCE_PRIORITY[source_type]
    if source_type.startswith("mes_"):
        return SOURCE_PRIORITY["mes_evidence"]
    return 0


def should_replace_source(existing: dict | None, new_source_type: str) -> bool:
    if existing is None:
        return True
    return _source_priority(new_source_type) >= _source_priority(existing.get("source_type"))


def _has_table(db: Session, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except Exception:
        return True


def _set_value(facts: TemplateDailyFacts, key: str, value: Any, source_type: str, **source_extra: Any) -> None:
    if value is None or value == "":
        return
    if not should_replace_source(facts.sources.get(key), source_type):
        return
    if isinstance(value, float):
        value = round(value, 3)
    facts.values[key] = value
    facts.sources[key] = _source(source_type, **source_extra)


def _set_missing_value(facts: TemplateDailyFacts, key: str, value: Any, source_type: str, **source_extra: Any) -> None:
    if facts.values.get(key) is not None:
        return
    _set_value(facts, key, value, source_type, **source_extra)


def _matches_any(value: Any, tokens: tuple[str, ...]) -> bool:
    text = str(value or "")
    return any(token and token in text for token in tokens)


def _wip_snapshot_weight_tons(value: Any) -> float:
    weight = _to_float(value)
    if weight > 1000:
        return weight / 1000
    return weight


def _wip_bucket(workshop_name: Any, process_name: Any) -> str | None:
    workshop = str(workshop_name or "")
    process = str(process_name or "")
    text = f"{workshop} {process}"
    if "园区在线" in workshop:
        return "wip_park_anneal"
    if "北线" in process and "园区" not in workshop:
        return "wip_new_north"
    if "南线" in process and "园区" not in workshop:
        return "wip_new_south"
    if ("1650" in workshop or "2050" in workshop) and "冷轧" in process:
        return "wip_1650_2050_cold"
    if "1850" in workshop and "冷轧" in process:
        return "wip_1850_cold"
    if "铣床" in text:
        return "wip_milling"
    if "拉矫" in workshop:
        return "wip_straightening"
    if workshop.strip() == "精整":
        return "wip_finishing"
    if "园区精整" in workshop:
        return "wip_park_finishing"
    if "热轧" in workshop and "中厚板剪切" in process:
        return "wip_hot_plate_shearing"
    if "彩涂" in workshop:
        return "wip_coating"
    return None


def _wip_breakdown_from_total_snapshots(db: Session, business_date: date) -> dict[str, float]:
    values = {key: 0.0 for key in WIP_BREAKDOWN_FIELDS}
    if not hasattr(db, "query"):
        return {}
    if not _has_table(db, MesWipTotalSnapshot.__tablename__):
        return {}
    try:
        start_at, end_at = production_business_window(business_date)
        rows = (
            db.query(
                MesWipTotalSnapshot.workshop_name,
                MesWipTotalSnapshot.process_name,
                func.sum(MesWipTotalSnapshot.doing_weight_tons),
            )
            .filter(MesWipTotalSnapshot.snapshot_at >= start_at, MesWipTotalSnapshot.snapshot_at < end_at)
            .group_by(MesWipTotalSnapshot.workshop_name, MesWipTotalSnapshot.process_name)
            .all()
        )
    except (OperationalError, ProgrammingError):
        return {}
    if not rows:
        return {}
    for workshop, process, weight in rows:
        bucket = _wip_bucket(workshop, process)
        if bucket is not None:
            values[bucket] += _wip_snapshot_weight_tons(weight)
    values["wip_anneal_total"] = values["wip_new_north"] + values["wip_new_south"] + values["wip_park_anneal"]
    values["wip_finishing_total"] = values["wip_straightening"] + values["wip_finishing"] + values["wip_park_finishing"]
    values["wip_total"] = (
        values["wip_1650_2050_cold"]
        + values["wip_1850_cold"]
        + values["wip_milling"]
        + values["wip_anneal_total"]
        + values["wip_finishing_total"]
        + values["wip_hot_plate_shearing"]
        + values["wip_coating"]
    )
    return {key: round(value, 3) for key, value in values.items()}


def _wip_breakdown_from_daily_snapshots(db: Session, business_date: date) -> dict[str, float]:
    values = {key: 0.0 for key in WIP_BREAKDOWN_FIELDS}
    if not hasattr(db, "query"):
        return {}
    if not _has_table(db, MesDailyWipSnapshot.__tablename__):
        return {}
    try:
        rows = (
            db.query(
                MesDailyWipSnapshot.workshop_name,
                MesDailyWipSnapshot.process_name,
                func.sum(MesDailyWipSnapshot.material_weight_tons),
            )
            .filter(MesDailyWipSnapshot.business_date == business_date)
            .filter(
                or_(
                    MesDailyWipSnapshot.source.is_(None),
                    MesDailyWipSnapshot.source != "output_skill_daily_report",
                )
            )
            .group_by(MesDailyWipSnapshot.workshop_name, MesDailyWipSnapshot.process_name)
            .all()
        )
    except (OperationalError, ProgrammingError):
        return {}
    if not rows:
        return {}
    for workshop, process, weight in rows:
        bucket = _wip_bucket(workshop, process)
        if bucket is not None:
            values[bucket] += _wip_snapshot_weight_tons(weight)
    values["wip_anneal_total"] = values["wip_new_north"] + values["wip_new_south"] + values["wip_park_anneal"]
    values["wip_finishing_total"] = values["wip_straightening"] + values["wip_finishing"] + values["wip_park_finishing"]
    values["wip_total"] = (
        values["wip_1650_2050_cold"]
        + values["wip_1850_cold"]
        + values["wip_milling"]
        + values["wip_anneal_total"]
        + values["wip_finishing_total"]
        + values["wip_hot_plate_shearing"]
        + values["wip_coating"]
    )
    if values["wip_total"] <= 0:
        return {}
    return {key: round(value, 3) for key, value in values.items()}


def _wip_breakdown_from_coil_snapshots(db: Session, business_date: date) -> dict[str, float]:
    values = {key: 0.0 for key in WIP_BREAKDOWN_FIELDS}
    if not hasattr(db, "query"):
        return {}
    if not _has_table(db, MesCoilSnapshot.__tablename__):
        return {}
    try:
        def present(column):
            return and_(column.isnot(None), column != "")

        workshop_label = func.coalesce(
            func.nullif(MesCoilSnapshot.current_workshop, ""),
            func.nullif(MesCoilSnapshot.workshop_code, ""),
            func.nullif(MesCoilSnapshot.next_process, ""),
        )
        process_label = func.coalesce(
            func.nullif(MesCoilSnapshot.current_process, ""),
            func.nullif(MesCoilSnapshot.next_process, ""),
            "",
        )
        not_finished_stock = and_(
            MesCoilSnapshot.in_stock_date.is_(None),
            or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != "已入库"),
        )
        rows = (
            db.query(workshop_label, process_label, func.sum(MesCoilSnapshot.material_weight))
            .filter(
                MesCoilSnapshot.business_date == business_date,
                MesCoilSnapshot.delivery_date.is_(None),
                MesCoilSnapshot.allocation_date.is_(None),
                not_finished_stock,
                or_(present(MesCoilSnapshot.current_process), present(MesCoilSnapshot.next_process)),
            )
            .group_by(workshop_label, process_label)
            .all()
        )
    except (OperationalError, ProgrammingError):
        return {}
    if not rows:
        return {}
    for workshop, process, weight in rows:
        bucket = _wip_bucket(workshop, process)
        if bucket is not None:
            values[bucket] += _to_float(weight) / 1000
    values["wip_anneal_total"] = values["wip_new_north"] + values["wip_new_south"] + values["wip_park_anneal"]
    values["wip_finishing_total"] = values["wip_straightening"] + values["wip_finishing"] + values["wip_park_finishing"]
    values["wip_total"] = (
        values["wip_1650_2050_cold"]
        + values["wip_1850_cold"]
        + values["wip_milling"]
        + values["wip_anneal_total"]
        + values["wip_finishing_total"]
        + values["wip_hot_plate_shearing"]
        + values["wip_coating"]
    )
    if values["wip_total"] <= 0:
        return {}
    return {key: round(value, 3) for key, value in values.items()}


def _row_text(row: MesWorkshopProcessRecord) -> str:
    payload = row.source_payload or {}
    payload_text = " ".join(str(payload.get(key) or "") for key in ("process_code", "report_process_code", "metric_code"))
    return " ".join(
        str(item or "")
        for item in (row.workshop_name, row.process_name, row.device_name, row.source_id, payload_text)
    )


def _output_weight_tons(row: MesWorkshopProcessRecord) -> float:
    direct = _to_float(row.output_weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.output_weight_kg) / 1000


def _pass_count(row: MesWorkshopProcessRecord) -> int:
    payload = row.source_payload or {}
    for key in ("pass_count", "passes", "道次"):
        if payload.get(key) not in (None, ""):
            return int(_to_float(payload.get(key)))
    return 1


def _query_manual_mobile_output(
    db: Session,
    *,
    start: date,
    end: date,
    tokens: tuple[str, ...],
) -> tuple[float | None, int]:
    if not _has_table(db, WorkOrderEntry.__tablename__):
        return None, 0
    rows = (
        db.query(WorkOrderEntry, Workshop)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_type == "mobile_coil",
            WorkOrderEntry.entry_status.in_(SUBMITTED_STATUSES),
            WorkOrderEntry.output_weight.isnot(None),
        )
        .all()
    )
    total = 0.0
    pass_total = 0
    matched = False
    for entry, workshop in rows:
        if not (_matches_any(workshop.name, tokens) or _matches_any(workshop.code, tokens)):
            continue
        matched = True
        total += _to_float(entry.output_weight) / 1000
        payload = entry.extra_payload or {}
        pass_total += int(_to_float(payload.get("pass_count")) or 0)
    return (round(total, 3), pass_total) if matched else (None, 0)


def _billet_material_business_window(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, BILLET_BUSINESS_DAY_START),
        datetime.combine(end + timedelta(days=1), BILLET_BUSINESS_DAY_START),
    )


def _material_weight_tons(row: MesMaterialRecord) -> float:
    direct = _to_float(row.weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.weight_kg) / 1000


def _material_status_text(row: MesMaterialRecord) -> str:
    payload = row.source_payload if isinstance(row.source_payload, dict) else {}
    return str(row.status_name or payload.get("StatusName") or payload.get("Status") or "").strip()


def _material_status_counts(row: MesMaterialRecord) -> bool:
    status_text = _material_status_text(row)
    if not status_text:
        return True
    return any(token in status_text for token in BILLET_MATERIAL_INCLUDED_STATUS_NAMES)


def _sum_mes_material_rows(
    rows: list[MesMaterialRecord],
    *,
    tokens: tuple[str, ...],
    prefer_explicit_status: bool,
) -> tuple[float | None, int]:
    matched: list[tuple[MesMaterialRecord, float]] = []
    for row in rows:
        if not _matches_any(row.workshop_name, tokens):
            continue
        weight = _material_weight_tons(row)
        if weight <= 0:
            continue
        matched.append((row, weight))
    if not matched:
        return None, 0

    require_explicit_status = prefer_explicit_status and any(_material_status_text(row) for row, _weight in matched)
    total = 0.0
    count = 0
    for row, weight in matched:
        if require_explicit_status and not _material_status_text(row):
            continue
        if not _material_status_counts(row):
            continue
        total += weight
        count += 1
    return (round(total, 3), count) if count else (None, 0)


def _query_mes_material_output(
    db: Session,
    *,
    start: date,
    end: date,
    tokens: tuple[str, ...],
) -> tuple[float | None, int]:
    if not hasattr(db, "query"):
        return None, 0
    if not _has_table(db, MesMaterialRecord.__tablename__):
        return None, 0

    business_date_rows = (
        db.query(MesMaterialRecord)
        .filter(
            MesMaterialRecord.business_date >= start,
            MesMaterialRecord.business_date <= end,
        )
        .order_by(MesMaterialRecord.id.asc())
        .all()
    )
    if business_date_rows:
        return _sum_mes_material_rows(
            business_date_rows,
            tokens=tokens,
            prefer_explicit_status=False,
        )

    day_start = datetime.combine(start, time.min)
    day_end = datetime.combine(end + timedelta(days=1), time.min)
    rows = (
        db.query(MesMaterialRecord)
        .filter(
            MesMaterialRecord.production_date >= day_start,
            MesMaterialRecord.production_date < day_end,
        )
        .order_by(MesMaterialRecord.id.asc())
        .all()
    )
    return _sum_mes_material_rows(
        rows,
        tokens=tokens,
        prefer_explicit_status=True,
    )


def _mes_rows(db: Session, *, start: date, end: date) -> list[MesWorkshopProcessRecord]:
    if not _has_table(db, MesWorkshopProcessRecord.__tablename__):
        return []
    return (
        db.query(MesWorkshopProcessRecord)
        .filter(MesWorkshopProcessRecord.business_date >= start, MesWorkshopProcessRecord.business_date <= end)
        .order_by(MesWorkshopProcessRecord.id.asc())
        .all()
    )


def _mapped_mes_output(
    rows: list[MesWorkshopProcessRecord],
    mapping: dict[str, Any],
    *,
    claimed_source_ids: set[str] | None = None,
) -> tuple[float | None, int, int]:
    total = 0.0
    pass_total = 0
    count = 0
    claimed_source_ids = claimed_source_ids if claimed_source_ids is not None else set()
    includes = tuple(mapping.get("include") or ())
    excludes = tuple(mapping.get("exclude") or ())
    device_includes = tuple(mapping.get("device_include") or ())
    for row in rows:
        source_key = row.source_id or str(row.id)
        if source_key in claimed_source_ids:
            continue
        text = _row_text(row)
        device_text = str(getattr(row, "device_name", "") or "")
        if device_includes and any(token in device_text for token in ("1650", "1850", "2050")):
            if not any(token in device_text for token in device_includes):
                continue
        else:
            if includes and not any(token in text for token in includes):
                continue
            if excludes and any(token in text for token in excludes):
                continue
        total += _output_weight_tons(row)
        pass_total += _pass_count(row)
        count += 1
        claimed_source_ids.add(source_key)
    if count:
        return round(total, 3), pass_total, count
    return (0.0, 0, 0) if rows else (None, 0, 0)


def _bucketed_mes_output(
    rows: list[MesWorkshopProcessRecord],
    buckets: tuple[str, ...],
    *,
    claimed_source_ids: set[str] | None = None,
) -> tuple[float | None, int, int]:
    total = 0.0
    pass_total = 0
    count = 0
    claimed_source_ids = claimed_source_ids if claimed_source_ids is not None else set()
    for row in rows:
        source_key = row.source_id or str(row.id)
        if source_key in claimed_source_ids:
            continue
        bucket = resolve_mes_process_workshop_bucket(row.workshop_name, row.process_name, row.device_name)
        if bucket not in buckets:
            continue
        total += _output_weight_tons(row)
        pass_total += _pass_count(row)
        count += 1
        claimed_source_ids.add(source_key)
    if count:
        return round(total, 3), pass_total, count
    return (0.0, 0, 0) if rows else (None, 0, 0)


def _owner_daily_payload_values(db: Session, *, target_date: date) -> dict[str, Any]:
    if not _has_table(db, WorkOrderEntry.__tablename__):
        return {}
    rows = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date == target_date,
            WorkOrderEntry.entry_type == "owner_daily",
            WorkOrderEntry.entry_status.in_(SUBMITTED_STATUSES),
        )
        .order_by(WorkOrderEntry.updated_at.asc(), WorkOrderEntry.id.asc())
        .all()
    )
    values: dict[str, Any] = {}
    for row in rows:
        payload = dict(row.extra_payload or {})
        values.update({key: value for key, value in payload.items() if value not in (None, "")})
    return values


def _copy_owner_values(facts: TemplateDailyFacts, owner_payload: dict[str, Any], required_fields: tuple[str, ...]) -> None:
    for key in required_fields:
        if key in MANUAL_OUTPUT_FIELDS:
            continue
        for source_key in (key, *OWNER_FIELD_ALIASES.get(key, ())):
            if source_key in owner_payload:
                _set_missing_value(facts, key, _to_float(owner_payload[source_key]), "owner_daily", field=source_key)
                break


def _owner_month_sum(
    db: Session,
    *,
    start: date,
    end: date,
    source_keys: tuple[str, ...],
) -> float | None:
    if not _has_table(db, WorkOrderEntry.__tablename__):
        return None
    rows = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_type == "owner_daily",
            WorkOrderEntry.entry_status.in_(SUBMITTED_STATUSES),
        )
        .order_by(WorkOrderEntry.business_date.asc(), WorkOrderEntry.updated_at.asc(), WorkOrderEntry.id.asc())
        .all()
    )
    total = 0.0
    found = False
    for row in rows:
        payload = dict(row.extra_payload or {})
        for source_key in source_keys:
            if payload.get(source_key) in (None, ""):
                continue
            total += _to_float(payload[source_key])
            found = True
            break
    return round(total, 3) if found else None


def collect_owner_rollup_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    for target_field, source_keys in OWNER_MONTH_SUM_ALIASES.items():
        if facts.values.get(target_field) is not None:
            continue
        value = _owner_month_sum(db, start=month_start, end=facts.target_date, source_keys=source_keys)
        _set_value(facts, target_field, value, "owner_daily_month_sum", fields=list(source_keys))


def _quality_percent(value: Any) -> float | None:
    if value in (None, ""):
        return None
    raw = float(value)
    if raw < 0:
        return None
    percent = raw * 100 if raw <= 1.5 else raw
    if percent > 100:
        return None
    return round(percent, 2)


def _quality_code(row: QualityYieldDaily) -> str:
    return str(getattr(row, "workshop_code", "") or "").strip().upper()


def _quality_code_matches(code: str, tokens: set[str]) -> bool:
    return any(token and token in code for token in tokens)


def _latest_quality_rows_before(db: Session, target_date: date) -> dict[str, QualityYieldDaily]:
    rows = (
        db.query(QualityYieldDaily)
        .filter(QualityYieldDaily.business_date < target_date)
        .order_by(QualityYieldDaily.business_date.desc(), QualityYieldDaily.id.desc())
        .all()
    )
    latest: dict[str, QualityYieldDaily] = {}
    for row in rows:
        latest.setdefault(_quality_code(row), row)
    return latest


def collect_quality_yield_facts(db: Session, facts: TemplateDailyFacts) -> None:
    if not _has_table(db, QualityYieldDaily.__tablename__):
        return
    try:
        rows = (
            db.query(QualityYieldDaily)
            .filter(QualityYieldDaily.business_date == facts.target_date)
            .order_by(QualityYieldDaily.id.asc())
            .all()
        )
        previous_by_code = _latest_quality_rows_before(db, facts.target_date)
    except (OperationalError, ProgrammingError):
        db.rollback()
        return

    for row in rows:
        code = _quality_code(row)
        daily = _quality_percent(row.yield_daily)
        monthly = _quality_percent(row.yield_monthly)
        target_m = _quality_percent(row.yield_target_m)
        target_casting = _quality_percent(row.yield_target_p_casting)
        target_hot_roll = _quality_percent(row.yield_target_p_hot_roll)
        overall = _quality_percent(row.yield_overall_company)

        if _quality_code_matches(code, QUALITY_FACTORY_CODES):
            _set_value(facts, "daily_yield_rate", daily or overall, "quality_yield_daily", workshop_code=row.workshop_code)
            _set_value(facts, "monthly_yield_rate", monthly or target_m, "quality_yield_daily", workshop_code=row.workshop_code)
        if _quality_code_matches(code, QUALITY_HOT_ROLL_CODES):
            _set_value(facts, "hot_roll_yield_rate", daily, "quality_yield_daily", workshop_code=row.workshop_code)
            _set_value(facts, "hot_roll_monthly_yield_rate", monthly or target_hot_roll, "quality_yield_daily", workshop_code=row.workshop_code)
            previous = previous_by_code.get(code)
            previous_daily = _quality_percent(previous.yield_daily) if previous is not None else None
            if daily is not None and previous_daily is not None:
                _set_value(
                    facts,
                    "hot_roll_yield_delta",
                    round(daily - previous_daily, 3),
                    "quality_yield_daily",
                    workshop_code=row.workshop_code,
                    comparison="previous_business_date",
                )
        if _quality_code_matches(code, QUALITY_CAST_ROLL_CODES):
            _set_value(facts, "cast_roll_yield_rate", monthly or daily, "quality_yield_daily", workshop_code=row.workshop_code)
        if _quality_code_matches(code, QUALITY_PLATE_COIL_CODES):
            _set_value(facts, "plate_coil_yield_rate", monthly or daily, "quality_yield_daily", workshop_code=row.workshop_code)

        _set_missing_value(facts, "monthly_yield_rate", target_m, "quality_yield_daily", workshop_code=row.workshop_code)
        _set_missing_value(facts, "cast_roll_yield_rate", target_casting, "quality_yield_daily", workshop_code=row.workshop_code)
        _set_missing_value(facts, "plate_coil_yield_rate", target_casting, "quality_yield_daily", workshop_code=row.workshop_code)
        _set_missing_value(facts, "hot_roll_monthly_yield_rate", target_hot_roll, "quality_yield_daily", workshop_code=row.workshop_code)


def collect_opening_facts(db: Session, facts: TemplateDailyFacts, *, wip_date: date | None = None) -> None:
    effective_wip_date = wip_date or facts.wip_date or facts.target_date
    facts.wip_date = effective_wip_date
    try:
        overview = daily_overview_builder.build_daily_production_overview(
            db,
            target_date=facts.target_date,
            wip_date=effective_wip_date,
        )
    except Exception as exc:
        facts.conflicts.append({"field": "daily_overview", "reason": type(exc).__name__})
        return

    plant_output = dict(overview.get("plant_output") or {})
    contracts = dict(overview.get("contracts") or {})
    yield_rates = dict(overview.get("yield_rates") or {})
    energy = dict(overview.get("energy") or {})
    cost = dict(overview.get("cost") or {})
    wip_distribution = list(overview.get("wip_distribution") or [])

    output_source_extra = {
        "source_table": plant_output.get("source_table"),
        "date_column": plant_output.get("date_column"),
    }
    inbound_source_extra = {
        "source_table": "WMS_InStock" if plant_output.get("finished_inbound_source") == "mes_stock_header_records" else None,
        "date_column": "InStockDate" if plant_output.get("finished_inbound_source") == "mes_stock_header_records" else None,
    }
    _set_value(facts, "total_output_daily", plant_output.get("daily_output"), "mes_packaging_output", **output_source_extra)
    _set_value(facts, "total_output_month", plant_output.get("monthly_output"), "mes_packaging_output", **output_source_extra)
    _set_value(
        facts,
        "total_output_delta",
        _to_float(plant_output.get("daily_output")) - _to_float(plant_output.get("yesterday_output")),
        "mes_packaging_output",
        **output_source_extra,
    )
    _set_value(
        facts,
        "finished_inbound_daily",
        plant_output.get("finished_inbound_output"),
        plant_output.get("finished_inbound_source") or "finished_inbound_output",
        **inbound_source_extra,
    )
    _set_value(
        facts,
        "finished_inbound_month",
        plant_output.get("finished_inbound_monthly_output"),
        plant_output.get("finished_inbound_source") or "finished_inbound_output",
        **inbound_source_extra,
    )
    shipment_totals = daily_overview_builder._query_mes_delivery_output_by_date(db, facts.target_date, facts.target_date)
    _set_value(facts, "shipment_daily", shipment_totals.get(facts.target_date), "mes_delivery_records")

    wip_total = sum(_to_float(row.get("total_weight")) for row in wip_distribution)
    if wip_total > 0:
        _set_value(
            facts,
            "wip_total",
            round(wip_total, 2),
            "mes_wip_distribution",
            business_date=overview.get("wip_business_date") or effective_wip_date.isoformat(),
        )
    wip_breakdown = _wip_breakdown_from_daily_snapshots(db, effective_wip_date)
    wip_breakdown_source = "mes_daily_wip_snapshot"
    if not wip_breakdown:
        wip_breakdown = _wip_breakdown_from_coil_snapshots(db, effective_wip_date)
        wip_breakdown_source = "mes_coil_snapshot_business_date"
    if not wip_breakdown:
        wip_breakdown = _wip_breakdown_from_total_snapshots(db, effective_wip_date)
        wip_breakdown_source = "mes_wip_total_snapshot"
    for key, value in wip_breakdown.items():
        _set_value(
            facts,
            key,
            value,
            wip_breakdown_source,
            business_date=overview.get("wip_business_date") or effective_wip_date.isoformat(),
        )

    _set_value(facts, "daily_contract_weight", contracts.get("daily_new"), "contract_projection")
    _set_value(facts, "remaining_contract_weight", contracts.get("remaining"), "contract_projection")
    _set_value(facts, "remaining_contract_delta", contracts.get("remaining_delta"), "contract_projection")
    _set_value(
        facts,
        "daily_yield_rate",
        _quality_percent(yield_rates.get("daily") or yield_rates.get("owner_daily")),
        "yield_projection",
    )
    _set_value(facts, "daily_yield_delta", yield_rates.get("daily_delta"), "yield_projection")
    _set_value(facts, "monthly_yield_rate", _quality_percent(yield_rates.get("monthly")), "yield_projection")
    _set_value(facts, "total_electricity_kwh", energy.get("total_electricity"), "owner_or_energy_summary")
    _set_value(facts, "total_gas_m3", energy.get("total_gas"), "owner_or_energy_summary")
    _set_value(facts, "electricity_cost_10k", cost.get("electricity_cost"), "energy_cost")
    _set_value(facts, "gas_cost_10k", cost.get("gas_cost"), "energy_cost")
    _set_value(facts, "total_cost_10k", cost.get("total"), "energy_cost")
    _set_value(facts, "cost_per_ton", cost.get("cost_per_ton"), "energy_cost")
    _set_value(facts, "cost_basis_weight", cost.get("basis_weight"), "energy_cost")


def collect_manual_workshop_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    for key, tokens in MANUAL_OUTPUT_WORKSHOPS.items():
        if key in facts.values:
            continue
        daily, _daily_pass = _query_manual_mobile_output(db, start=facts.target_date, end=facts.target_date, tokens=tokens)
        monthly, _monthly_pass = _query_manual_mobile_output(db, start=month_start, end=facts.target_date, tokens=tokens)
        _set_value(facts, key, daily, "manual_mobile_coil")
        _set_value(facts, MONTHLY_FIELD_BY_DAILY_FIELD[key], monthly, "manual_mobile_coil")


def collect_mes_material_workshop_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    for key, tokens in MES_MATERIAL_OUTPUT_WORKSHOPS.items():
        daily, daily_count = _query_mes_material_output(db, start=facts.target_date, end=facts.target_date, tokens=tokens)
        monthly, monthly_count = _query_mes_material_output(db, start=month_start, end=facts.target_date, tokens=tokens)
        _set_value(facts, key, daily, "mes_material_records", basis="ProductionDate 08:00-08:00", roll_count=daily_count)
        _set_value(
            facts,
            MONTHLY_FIELD_BY_DAILY_FIELD[key],
            monthly,
            "mes_material_records",
            basis="ProductionDate 08:00-08:00",
            roll_count=monthly_count,
        )


def collect_mes_workshop_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    daily_rows = _mes_rows(db, start=facts.target_date, end=facts.target_date)
    month_rows = _mes_rows(db, start=month_start, end=facts.target_date)
    claimed_daily: set[str] = set()
    claimed_month: set[str] = set()

    for key, buckets in MES_REPORT_PROCESS_BUCKETS.items():
        if key in BILLET_MATERIAL_FIELDS:
            continue
        daily, daily_pass, _daily_count = _bucketed_mes_output(daily_rows, buckets, claimed_source_ids=claimed_daily)
        monthly, monthly_pass, _monthly_count = _bucketed_mes_output(month_rows, buckets, claimed_source_ids=claimed_month)
        _set_value(facts, key, daily, "mes_workshop_process_records")
        _set_value(facts, MONTHLY_FIELD_BY_DAILY_FIELD[key], monthly, "mes_workshop_process_records")
        _set_value(facts, key.replace("_daily", "_pass_daily"), daily_pass, "computed")
        _set_value(facts, key.replace("_daily", "_pass_month"), monthly_pass, "computed")

    cast_2 = facts.values.get("cast_2_daily")
    cast_3 = facts.values.get("cast_3_daily")
    if facts.values.get("cast_roll_daily") is None and (cast_2 is not None or cast_3 is not None):
        _set_value(facts, "cast_roll_daily", _to_float(cast_2) + _to_float(cast_3), "computed")
    cast_2_month = facts.values.get("cast_2_month")
    cast_3_month = facts.values.get("cast_3_month")
    if facts.values.get("cast_roll_month") is None and (cast_2_month is not None or cast_3_month is not None):
        _set_value(facts, "cast_roll_month", _to_float(cast_2_month) + _to_float(cast_3_month), "computed")

    rolling_keys = ("cold_1650", "cold_1850", "cold_2050")
    if any(facts.values.get(f"{item}_daily") is not None for item in rolling_keys):
        _set_value(
            facts,
            "rolling_daily",
            sum(_to_float(facts.values.get(f"{item}_daily")) for item in rolling_keys),
            "computed",
        )
    if any(facts.values.get(f"{item}_month") is not None for item in rolling_keys):
        _set_value(
            facts,
            "rolling_month",
            sum(_to_float(facts.values.get(f"{item}_month")) for item in rolling_keys),
            "computed",
        )
    if any(facts.values.get(f"{item}_pass_daily") is not None for item in rolling_keys):
        _set_value(
            facts,
            "rolling_pass_daily",
            sum(_to_float(facts.values.get(f"{item}_pass_daily")) for item in rolling_keys),
            "computed",
        )
    if any(facts.values.get(f"{item}_pass_month") is not None for item in rolling_keys):
        _set_value(
            facts,
            "rolling_pass_month",
            sum(_to_float(facts.values.get(f"{item}_pass_month")) for item in rolling_keys),
            "computed",
        )


def collect_recovery_and_overhaul_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    try:
        if _has_table(db, RecoveryDaily.__tablename__):
            row = db.query(RecoveryDaily).filter(RecoveryDaily.business_date == facts.target_date).one_or_none()
            monthly = (
                db.query(func.sum(RecoveryDaily.recovery_output_tons))
                .filter(RecoveryDaily.business_date >= month_start, RecoveryDaily.business_date <= facts.target_date)
                .scalar()
            )
            if row is not None and facts.values.get("recovery_daily") is None:
                _set_value(facts, "recovery_daily", row.recovery_output_tons, "recovery_daily")
            _set_value(facts, "recovery_month", monthly, "recovery_daily")
        if _has_table(db, OverhaulDaily.__tablename__):
            row = db.query(OverhaulDaily).filter(OverhaulDaily.business_date == facts.target_date).one_or_none()
            monthly = (
                db.query(func.sum(OverhaulDaily.roller_grind_count))
                .filter(OverhaulDaily.business_date >= month_start, OverhaulDaily.business_date <= facts.target_date)
                .scalar()
            )
            if row is not None and facts.values.get("roller_grind_daily") is None:
                _set_value(facts, "roller_grind_daily", row.roller_grind_count, "overhaul_daily")
            _set_value(facts, "roller_grind_month", monthly, "overhaul_daily")
    except (OperationalError, ProgrammingError):
        return


def collect_yesterday_comparison_facts(db: Session, facts: TemplateDailyFacts) -> None:
    if not _has_table(db, DailyReport.__tablename__):
        return
    previous = (
        db.query(DailyReport)
        .filter(DailyReport.report_date < facts.target_date, DailyReport.report_type == "production")
        .order_by(DailyReport.report_date.desc(), DailyReport.id.desc())
        .first()
    )
    if previous is None or not previous.final_text_summary:
        return
    parsed = parse_output_skill_daily_report(previous.final_text_summary)
    if "total_output_daily" in facts.values and "total_output_daily" in parsed:
        _set_value(
            facts,
            "total_output_delta",
            round(_to_float(facts.values["total_output_daily"]) - _to_float(parsed["total_output_daily"]), 3),
            "previous_final_report",
            field="total_output_daily",
        )
    if "remaining_contract_weight" in facts.values and "remaining_contract_weight" in parsed:
        _set_value(
            facts,
            "remaining_contract_delta",
            round(_to_float(facts.values["remaining_contract_weight"]) - _to_float(parsed["remaining_contract_weight"]), 3),
            "previous_final_report",
            field="remaining_contract_weight",
        )
    if "daily_yield_rate" in facts.values and "daily_yield_rate" in parsed:
        _set_value(
            facts,
            "daily_yield_delta",
            round(_to_float(facts.values["daily_yield_rate"]) - _to_float(parsed["daily_yield_rate"]), 3),
            "previous_final_report",
            field="daily_yield_rate",
        )
    if "hot_roll_yield_rate" in facts.values and "hot_roll_yield_rate" in parsed:
        _set_value(
            facts,
            "hot_roll_yield_delta",
            round(_to_float(facts.values["hot_roll_yield_rate"]) - _to_float(parsed["hot_roll_yield_rate"]), 3),
            "previous_final_report",
            field="hot_roll_yield_rate",
        )


def collect_datahub_final_daily_report_facts(db: Session, facts: TemplateDailyFacts) -> None:
    reference = _datahub_final_daily_report_reference(db, facts.target_date)
    if reference is None:
        return
    parsed = parse_output_skill_daily_report(str(reference.get("text") or ""))
    if not parsed:
        return
    source_extra = {
        "source_table": reference.get("source_table"),
        "source_payload_key": reference.get("source_payload_key"),
        "report_id": reference.get("report_id"),
        "business_date": facts.target_date.isoformat(),
    }
    for field_name, value in parsed.items():
        _set_value(facts, field_name, value, "datahub_final_daily_report", **source_extra)


def _datahub_final_daily_report_reference(db: Session, target_date: date) -> dict[str, Any] | None:
    if not hasattr(db, "query"):
        return None
    if _has_table(db, DailyReport.__tablename__):
        try:
            row = (
                db.query(DailyReport)
                .filter(DailyReport.report_date == target_date)
                .filter(DailyReport.report_type == "production")
                .order_by(
                    DailyReport.final_confirmed_at.desc(),
                    DailyReport.published_at.desc(),
                    DailyReport.id.desc(),
                )
                .first()
            )
        except (OperationalError, ProgrammingError):
            db.rollback()
            row = None
        if row is not None and str(row.final_text_summary or "").strip():
            return {
                "source_table": DailyReport.__tablename__,
                "report_id": row.id,
                "text": row.final_text_summary,
            }
        template_reference = _datahub_template_daily_report_reference(row)
        if template_reference is not None:
            return template_reference

    if _has_table(db, DailyReportHistoryRecord.__tablename__):
        try:
            history = (
                db.query(DailyReportHistoryRecord)
                .filter(DailyReportHistoryRecord.report_type == "daily")
                .filter(DailyReportHistoryRecord.business_date == target_date)
                .order_by(DailyReportHistoryRecord.created_at.desc(), DailyReportHistoryRecord.id.desc())
                .first()
            )
        except (OperationalError, ProgrammingError):
            db.rollback()
            history = None
        if history is not None and str(history.report_text or "").strip():
            return {
                "source_table": DailyReportHistoryRecord.__tablename__,
                "report_id": history.id,
                "text": history.report_text,
            }
    return None


def _datahub_template_daily_report_reference(row: DailyReport | None) -> dict[str, Any] | None:
    if row is None:
        return None
    report_data = row.report_data if isinstance(row.report_data, dict) else {}
    payload = report_data.get(DATAHUB_TEMPLATE_REPORT_KEY)
    if not isinstance(payload, dict):
        return None
    if str(payload.get("status") or "").strip().lower() != "ready":
        return None
    text = str(payload.get("text") or "").strip()
    if not text:
        return None
    return {
        "source_table": DailyReport.__tablename__,
        "source_payload_key": DATAHUB_TEMPLATE_REPORT_KEY,
        "report_id": row.id,
        "text": text,
    }


def collect_template_daily_facts(
    db: Session,
    *,
    target_date: date,
    wip_date: date | None = None,
    required_fields: tuple[str, ...],
) -> TemplateDailyFacts:
    effective_wip_date = wip_date or (target_date + timedelta(days=1))
    facts = TemplateDailyFacts(target_date=target_date, wip_date=effective_wip_date)
    _set_value(facts, "report_date", target_date, "runtime_target_date")

    collect_opening_facts(db, facts, wip_date=effective_wip_date)
    _copy_owner_values(facts, _owner_daily_payload_values(db, target_date=target_date), required_fields)
    collect_owner_rollup_facts(db, facts)
    collect_mes_material_workshop_facts(db, facts)
    collect_mes_workshop_facts(db, facts)
    collect_recovery_and_overhaul_facts(db, facts)
    collect_quality_yield_facts(db, facts)
    collect_yesterday_comparison_facts(db, facts)
    collect_datahub_final_daily_report_facts(db, facts)

    facts.missing_fields = [key for key in required_fields if facts.values.get(key) is None]
    return facts
