from __future__ import annotations

import copy
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any, Callable

from sqlalchemy import and_, func, inspect, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.active_workshops import normalize_workshop_name
from app.core.business_time import local_now, production_business_window
from app.domain.daily_report_field_contract import (
    DAILY_REPORT_FIELD_CONTRACT_VERSION,
    source_lane_priority,
)
from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACT_VERSION
from app.models.energy import EnergyImportRecord
from app.models.imports import ImportBatch, ImportedDailyMetricFact, ImportRow
from app.models.master import Equipment, Workshop
from app.models.mes import (
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMaterialRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
)
from app.models.production import OverhaulDaily, RecoveryDaily, ShiftProductionData, WorkOrderEntry
from app.models.quality import QualityYieldDaily
from app.models.reports import DailyReport, DailyReportHistoryRecord
from app.services.daily_energy_report_service import daily_energy_report_fact_field
from app.services.daily_production_canonical_service import daily_production_lineage_is_valid
from app.services.daily_production_mapping_service import (
    DailyProductionMappingRow,
    build_daily_production_mapping_preview,
)
from app.services.report import daily_overview_builder
from app.services.report._utils import _to_float
from app.services.report.mes_workshop_mapping import resolve_mes_process_workshop_bucket
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


SUBMITTED_STATUSES = ("submitted", "verified", "approved")
DATAHUB_TEMPLATE_REPORT_KEY = "template_daily_report"
SOURCE_PRIORITY = {
    source_type: source_lane_priority(source_type)
    for source_type in (
        "owner_daily",
        "manual_workbook",
        "wms_direct",
        "mes_verified",
        "manual_mobile_coil",
        "owner_daily_month_sum",
        "quality_yield_daily",
        "recovery_daily",
        "overhaul_daily",
        "mes_stock_header_records",
        "mes_stock_records",
        "mes_stock_records_missing",
        "finished_inbound_output",
        "datahub_final_daily_report",
        "previous_final_report",
        "computed",
        "owner_or_energy_summary",
        "energy_cost",
        "contract_projection",
        "yield_projection",
        "mes_packaging_output",
        "mes_delivery_records",
        "mes_wip_distribution",
        "mes_daily_wip_snapshot",
        "mes_coil_snapshot_business_date",
        "mes_wip_total_snapshot",
        "mes_material_records",
        "mes_workshop_process_records",
        "runtime_target_date",
        "mes_evidence",
    )
}

MANUAL_OUTPUT_WORKSHOPS = {
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

PASS_FIELDS_BY_DAILY_FIELD = {
    "cold_1650_daily": ("cold_1650_pass_daily", "cold_1650_pass_month"),
    "cold_1850_daily": ("cold_1850_pass_daily", "cold_1850_pass_month"),
    "cold_2050_daily": ("cold_2050_pass_daily", "cold_2050_pass_month"),
}

IMPORTED_PRODUCTION_FIELD_BY_EQUIPMENT = {
    "RZ-ZJ": "hot_roll_daily",
    "LZ1650-1": "cold_1650_daily",
    "LZ1850-1": "cold_1850_daily",
    "LZ2050-1": "cold_2050_daily",
    "JQ-LJ": "straightening_daily",
    "ZXTF-1": "online_anneal_daily",
    "ZXTF-2": "online_anneal_daily",
    "ZXTF-3": "online_anneal_daily",
    "ZXTF-4": "online_anneal_daily",
}

IMPORTED_PRODUCTION_FIELD_BY_WORKSHOP = {
    "ZD": "foundry_daily",
    "ZR2": "cast_2_daily",
    "ZR3": "cast_3_daily",
}

OWNER_FIELD_ALIASES = {
    "daily_yield_rate": ("daily_yield_rate", "plant_wide_yield_rate"),
    "hot_roll_furnace_gas_m3": ("hot_roll_furnace_gas_m3", "heating_furnace_gas_m3"),
    "hot_roll_boiler_gas_m3": ("hot_roll_boiler_gas_m3", "boiler_gas_m3"),
    "cold_roll_input_daily": ("cold_roll_input_daily", "daily_input_weight"),
    "recovery_daily": ("recovery_daily", "recovery_weight", "recovery_output_tons"),
    "roller_grind_daily": ("roller_grind_daily", "roller_grinding_count"),
}

OWNER_MONTH_SUM_ALIASES = {
    "recovery_month": ("recovery_month", "recovery_weight", "recovery_daily", "recovery_output_tons"),
    "roller_grind_month": ("roller_grind_month", "roller_grinding_count", "roller_grind_daily"),
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
    return source_lane_priority(source_type)


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
    if isinstance(value, Decimal) and not value.is_finite():
        return
    if isinstance(value, float) and not math.isfinite(value):
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


def _wip_distribution_source(
    rows: list[dict[str, Any]],
    *,
    business_date: date,
) -> tuple[str, dict[str, Any]]:
    source_types = {
        str(row.get("source_basis") or "").strip()
        for row in rows
        if row.get("source_basis")
    }
    source_type = next(iter(source_types)) if len(source_types) == 1 else "mes_wip_distribution"
    detail: dict[str, Any] = {"business_date": business_date.isoformat()}
    source_refs = {
        "mes_wip_total_snapshot": "mes_wip_total_snapshots",
        "mes_daily_wip_snapshot": "mes_daily_wip_snapshots",
        "mes_coil_snapshot_business_date": "mes_coil_snapshots",
    }
    snapshot_values = [
        str(row.get("snapshot_at") or "").strip()
        for row in rows
        if row.get("snapshot_at")
    ]
    source_ref = source_refs.get(source_type)
    if not source_ref or not snapshot_values:
        return source_type, detail
    try:
        snapshot_at = max(local_now(datetime.fromisoformat(item)) for item in snapshot_values).isoformat()
    except ValueError:
        return source_type, detail
    row_count = len(rows)
    detail.update(
        {
            "source_ref": source_ref,
            "business_window": f"{snapshot_at}/{snapshot_at}",
            "snapshot_at": snapshot_at,
            "unit": "吨",
            "row_count": row_count,
            "trace_id": f"projection-read:{source_ref}:{snapshot_at}:{row_count}",
            "metric_contract_version": "2026-07-11",
        }
    )
    return source_type, detail


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


def _wip_snapshot_source_detail(
    db: Session,
    *,
    source_type: str,
    business_date: date,
    field_name: str,
    snapshot_rows: tuple[str, list[Any]] | None = None,
) -> dict[str, Any]:
    if not hasattr(db, "query"):
        return {}
    field_buckets = _wip_field_buckets(field_name)
    if not field_buckets:
        return {}
    source_ref, candidates = snapshot_rows or _wip_snapshot_rows(
        db,
        source_type=source_type,
        business_date=business_date,
    )
    if not source_ref:
        return {}
    selected = []
    for row in candidates:
        workshop = (
            getattr(row, "current_workshop", None)
            or getattr(row, "workshop_code", None)
            or getattr(row, "workshop_name", None)
        )
        process = (
            getattr(row, "current_process", None)
            or getattr(row, "next_process", None)
            or getattr(row, "process_name", None)
        )
        if _wip_bucket(workshop, process) not in field_buckets:
            continue
        weight = (
            _to_float(row.material_weight) / 1000
            if isinstance(row, MesCoilSnapshot)
            else _wip_snapshot_weight_tons(
                getattr(row, "material_weight_tons", None)
                if isinstance(row, MesDailyWipSnapshot)
                else getattr(row, "doing_weight_tons", None)
            )
        )
        if weight > 0:
            selected.append(row)
    if not selected:
        return {}
    row_count = len(selected)
    latest_row_id = max(int(row.id) for row in selected)
    snapshot_at = max(
        row.last_synced_at if isinstance(row, MesCoilSnapshot) else row.snapshot_at
        for row in selected
    )
    snapshot_text = local_now(snapshot_at).isoformat()
    return {
        "source_ref": source_ref,
        "business_window": f"{snapshot_text}/{snapshot_text}",
        "unit": "吨",
        "row_count": int(row_count),
        "latest_row_id": int(latest_row_id),
        "trace_id": f"projection-read:{source_ref}:{latest_row_id}:{int(row_count)}",
        "metric_contract_version": "2026-07-11",
    }


def _wip_snapshot_rows(
    db: Session,
    *,
    source_type: str,
    business_date: date,
) -> tuple[str, list[Any]]:
    if source_type == "mes_wip_total_snapshot":
        start_at, end_at = production_business_window(business_date)
        query = db.query(MesWipTotalSnapshot).filter(
            MesWipTotalSnapshot.snapshot_at >= start_at,
            MesWipTotalSnapshot.snapshot_at < end_at,
        )
        model = MesWipTotalSnapshot
        source_ref = MesWipTotalSnapshot.__tablename__
    elif source_type == "mes_daily_wip_snapshot":
        query = db.query(MesDailyWipSnapshot).filter(
            MesDailyWipSnapshot.business_date == business_date,
            or_(
                MesDailyWipSnapshot.source.is_(None),
                MesDailyWipSnapshot.source != "output_skill_daily_report",
            ),
        )
        model = MesDailyWipSnapshot
        source_ref = MesDailyWipSnapshot.__tablename__
    elif source_type == "mes_coil_snapshot_business_date":
        query = db.query(MesCoilSnapshot).filter(
            MesCoilSnapshot.business_date == business_date,
            MesCoilSnapshot.delivery_date.is_(None),
            MesCoilSnapshot.allocation_date.is_(None),
            MesCoilSnapshot.in_stock_date.is_(None),
            or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != "已入库"),
            or_(
                and_(MesCoilSnapshot.current_process.isnot(None), MesCoilSnapshot.current_process != ""),
                and_(MesCoilSnapshot.next_process.isnot(None), MesCoilSnapshot.next_process != ""),
            ),
        )
        model = MesCoilSnapshot
        source_ref = MesCoilSnapshot.__tablename__
    else:
        return "", []
    try:
        candidates = query.order_by(model.id.asc()).all()
    except (OperationalError, ProgrammingError):
        return "", []
    return source_ref, candidates


def _wip_field_buckets(field_name: str) -> set[str]:
    base_fields = set(WIP_BREAKDOWN_FIELDS)
    if field_name == "wip_total":
        return base_fields
    if field_name == "wip_anneal_total":
        return {"wip_new_north", "wip_new_south", "wip_park_anneal"}
    if field_name == "wip_finishing_total":
        return {"wip_straightening", "wip_finishing", "wip_park_finishing"}
    return {field_name} if field_name in base_fields else set()


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
    workshop_names: tuple[str, ...],
) -> tuple[float | None, int | None, int, int | None]:
    if not _has_table(db, WorkOrderEntry.__tablename__):
        return None, None, 0, None
    entries = daily_overview_builder._query_latest_mobile_coil_rows(db, start, end)
    workshop_ids = {entry.workshop_id for entry in entries if entry.workshop_id is not None}
    workshops_by_id = (
        {
            workshop.id: workshop
            for workshop in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()
        }
        if workshop_ids
        else {}
    )
    total = 0.0
    pass_total = 0
    pass_count_present = False
    row_count = 0
    latest_row_id: int | None = None
    accepted_workshops = {normalize_workshop_name(name) for name in workshop_names}
    for entry in entries:
        workshop = workshops_by_id.get(entry.workshop_id)
        if workshop is None:
            continue
        if normalize_workshop_name(workshop.name) not in accepted_workshops:
            continue
        row_count += 1
        if entry.id is not None:
            latest_row_id = max(latest_row_id or 0, int(entry.id))
        total += _to_float(entry.output_weight) / 1000
        payload = entry.extra_payload or {}
        if payload.get("pass_count") not in (None, ""):
            pass_count_present = True
            pass_total += int(_to_float(payload.get("pass_count")) or 0)
    if not row_count:
        return None, None, 0, None
    return round(total, 3), (pass_total if pass_count_present else None), row_count, latest_row_id


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
) -> tuple[float | None, int, int | None]:
    matched: list[tuple[MesMaterialRecord, float]] = []
    for row in rows:
        if not _matches_any(row.workshop_name, tokens):
            continue
        weight = _material_weight_tons(row)
        if weight <= 0:
            continue
        matched.append((row, weight))
    if not matched:
        return None, 0, None

    require_explicit_status = prefer_explicit_status and any(_material_status_text(row) for row, _weight in matched)
    total = 0.0
    count = 0
    latest_row_id: int | None = None
    for row, weight in matched:
        if require_explicit_status and not _material_status_text(row):
            continue
        if not _material_status_counts(row):
            continue
        total += weight
        count += 1
        if row.id is not None:
            latest_row_id = max(latest_row_id or 0, int(row.id))
    return (round(total, 3), count, latest_row_id) if count else (None, 0, None)


def _query_mes_material_output(
    db: Session,
    *,
    start: date,
    end: date,
    tokens: tuple[str, ...],
) -> tuple[float | None, int, int | None]:
    if not hasattr(db, "query"):
        return None, 0, None
    if not _has_table(db, MesMaterialRecord.__tablename__):
        return None, 0, None

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

    day_start, day_end = _billet_material_business_window(start, end)
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
) -> tuple[float | None, int | None, int, int | None]:
    total = 0.0
    pass_total = 0
    count = 0
    latest_row_id: int | None = None
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
        if row.id is not None:
            latest_row_id = max(latest_row_id or 0, int(row.id))
        claimed_source_ids.add(source_key)
    if count:
        return round(total, 3), pass_total, count, latest_row_id
    return None, None, 0, None


def _mes_workshop_source_detail(
    *,
    row_count: int,
    latest_row_id: int | None,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    detail = {
        "source_table": "MES_ProductProcessRecord",
        "source_ref": MesWorkshopProcessRecord.__tablename__,
        "business_window": f"{window_start.isoformat()}/{window_end.isoformat()}",
        "unit": "吨",
        "row_count": row_count,
        "metric_contract_version": "2026-07-11",
    }
    if row_count > 0 and latest_row_id is not None:
        detail.update(
            {
                "latest_row_id": latest_row_id,
                "trace_id": (
                    f"projection-read:{MesWorkshopProcessRecord.__tablename__}:"
                    f"{latest_row_id}:{row_count}"
                ),
            }
        )
    return detail


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
        for source_key in (key, *OWNER_FIELD_ALIASES.get(key, ())):
            if source_key in owner_payload:
                _set_value(facts, key, _to_float(owner_payload[source_key]), "owner_daily", field=source_key)
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
        "projection_table": plant_output.get("projection_table"),
        "date_column": plant_output.get("date_column"),
    }
    if (
        int(plant_output.get("row_count") or 0) > 0
        and plant_output.get("source_table")
        and plant_output.get("business_window_start")
        and plant_output.get("business_window_end")
        and plant_output.get("projection_table")
        and plant_output.get("latest_row_id") is not None
        and plant_output.get("source_trace_id")
    ):
        output_source_extra.update(
            {
                "source_ref": plant_output["projection_table"],
                "business_window": (
                    f"{plant_output['business_window_start']}/{plant_output['business_window_end']}"
                ),
                "unit": "吨",
                "row_count": int(plant_output["row_count"]),
                "latest_row_id": int(plant_output["latest_row_id"]),
                "trace_id": plant_output["source_trace_id"],
                "metric_contract_version": "2026-07-11",
            }
        )
    output_month_source_extra = {
        "source_table": plant_output.get("source_table"),
        "projection_table": plant_output.get("projection_table"),
        "date_column": plant_output.get("date_column"),
    }
    if (
        int(plant_output.get("month_row_count") or 0) > 0
        and plant_output.get("source_table")
        and plant_output.get("month_window_start")
        and plant_output.get("business_window_end")
        and plant_output.get("projection_table")
        and plant_output.get("month_latest_row_id") is not None
        and plant_output.get("source_month_trace_id")
    ):
        output_month_source_extra.update(
            {
                "source_ref": plant_output["projection_table"],
                "business_window": (
                    f"{plant_output['month_window_start']}/{plant_output['business_window_end']}"
                ),
                "unit": "吨",
                "row_count": int(plant_output["month_row_count"]),
                "latest_row_id": int(plant_output["month_latest_row_id"]),
                "trace_id": plant_output["source_month_trace_id"],
                "metric_contract_version": "2026-07-11",
            }
        )
    inbound_source = plant_output.get("finished_inbound_source")
    inbound_source_extra = {
        "source_table": (
            "WMS_InStock"
            if inbound_source == "mes_stock_header_records"
            else "WMS_InStockDetail"
            if inbound_source == "mes_stock_records"
            else None
        ),
        "projection_table": "mes_stock_records",
        "date_column": (
            "InStockDate"
            if inbound_source == "mes_stock_header_records"
            else "CreateDate"
            if inbound_source == "mes_stock_records"
            else None
        ),
    }
    inbound_month_source_extra = dict(inbound_source_extra)
    if (
        int(plant_output.get("finished_inbound_row_count") or 0) > 0
        and inbound_source_extra["source_table"]
        and plant_output.get("business_window_start")
        and plant_output.get("business_window_end")
        and plant_output.get("finished_inbound_latest_row_id") is not None
        and plant_output.get("finished_inbound_trace_id")
    ):
        inbound_source_extra.update(
            {
                "source_ref": inbound_source_extra["projection_table"],
                "business_window": (
                    f"{plant_output['business_window_start']}/{plant_output['business_window_end']}"
                ),
                "unit": "吨",
                "row_count": int(plant_output["finished_inbound_row_count"]),
                "latest_row_id": int(plant_output["finished_inbound_latest_row_id"]),
                "trace_id": plant_output["finished_inbound_trace_id"],
                "metric_contract_version": "2026-07-11",
            }
        )
    if (
        int(plant_output.get("finished_inbound_month_row_count") or 0) > 0
        and inbound_source_extra["source_table"]
        and plant_output.get("month_window_start")
        and plant_output.get("business_window_end")
        and plant_output.get("finished_inbound_month_latest_row_id") is not None
        and plant_output.get("finished_inbound_month_trace_id")
    ):
        inbound_month_source_extra.update(
            {
                "source_ref": inbound_source_extra["projection_table"],
                "business_window": (
                    f"{plant_output['month_window_start']}/{plant_output['business_window_end']}"
                ),
                "unit": "吨",
                "row_count": int(plant_output["finished_inbound_month_row_count"]),
                "latest_row_id": int(plant_output["finished_inbound_month_latest_row_id"]),
                "trace_id": plant_output["finished_inbound_month_trace_id"],
                "metric_contract_version": "2026-07-11",
            }
        )
    official_output = _official_template_total_output(db, facts.target_date, plant_output)
    output_row_count = plant_output.get("row_count")
    output_has_rows = output_row_count is None or int(output_row_count or 0) > 0
    if output_has_rows:
        _set_value(
            facts,
            "total_output_daily",
            official_output["daily"],
            official_output["source_type"],
            **output_source_extra,
        )
        _set_value(
            facts,
            "total_output_month",
            official_output["monthly"],
            official_output["source_type"],
            **output_month_source_extra,
        )
        _set_value(
            facts,
            "total_output_delta",
            official_output["delta"],
            "computed",
            formula="total_output_daily - previous_total_output_daily",
            components=[
                {
                    "field": "total_output_daily",
                    "business_date": facts.target_date.isoformat(),
                    "value": _to_float(official_output["daily"]),
                    "source_type": official_output["source_type"],
                    **(
                        {"source_ref": output_source_extra["source_ref"]}
                        if output_source_extra.get("source_ref")
                        else {}
                    ),
                },
                {
                    "field": "total_output_daily",
                    "business_date": (facts.target_date - timedelta(days=1)).isoformat(),
                    "value": _to_float(official_output["previous"]),
                    "source_type": "mes_packaging_output",
                    "source_ref": "mes_workshop_process_records",
                },
            ],
        )
    inbound_row_count = plant_output.get("finished_inbound_row_count")
    inbound_has_rows = inbound_row_count is None or int(inbound_row_count or 0) > 0
    if inbound_has_rows:
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
            **inbound_month_source_extra,
        )
    shipment_totals = daily_overview_builder._query_mes_delivery_output_by_date(db, facts.target_date, facts.target_date)
    _set_value(facts, "shipment_daily", shipment_totals.get(facts.target_date), "mes_delivery_records")

    wip_total = sum(_to_float(row.get("total_weight")) for row in wip_distribution)
    if wip_total > 0:
        wip_source_type, wip_source_detail = _wip_distribution_source(
            wip_distribution,
            business_date=effective_wip_date,
        )
        _set_value(
            facts,
            "wip_total",
            round(wip_total, 2),
            wip_source_type,
            **wip_source_detail,
        )
    wip_breakdown = _wip_breakdown_from_daily_snapshots(db, effective_wip_date)
    wip_breakdown_source = "mes_daily_wip_snapshot"
    if not wip_breakdown:
        wip_breakdown = _wip_breakdown_from_coil_snapshots(db, effective_wip_date)
        wip_breakdown_source = "mes_coil_snapshot_business_date"
    if not wip_breakdown:
        wip_breakdown = _wip_breakdown_from_total_snapshots(db, effective_wip_date)
        wip_breakdown_source = "mes_wip_total_snapshot"
    wip_source_detail = {
        "business_date": overview.get("wip_business_date") or effective_wip_date.isoformat(),
    }
    wip_snapshot_rows = (
        _wip_snapshot_rows(
            db,
            source_type=wip_breakdown_source,
            business_date=effective_wip_date,
        )
        if wip_breakdown and hasattr(db, "query")
        else ("", [])
    )
    for key, value in wip_breakdown.items():
        _set_value(
            facts,
            key,
            value,
            wip_breakdown_source,
            **wip_source_detail,
            **_wip_snapshot_source_detail(
                db,
                source_type=wip_breakdown_source,
                business_date=effective_wip_date,
                field_name=key,
                snapshot_rows=wip_snapshot_rows,
            ),
        )

    _set_value(facts, "daily_contract_weight", contracts.get("daily_new"), "contract_projection")
    _set_value(facts, "cold_roll_input_daily", contracts.get("daily_input"), "contract_projection")
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


def _official_template_total_output(
    db: Session,
    target_date: date,
    plant_output: dict[str, Any],
) -> dict[str, Any]:
    daily = plant_output.get("daily_output")
    monthly = plant_output.get("monthly_output")
    yesterday = plant_output.get("yesterday_output")
    if _to_float(yesterday) <= 0:
        previous_output = _packaging_output_for_date(db, target_date - timedelta(days=1))
        if previous_output is not None:
            yesterday = previous_output
    delta = None
    if daily not in (None, "") and yesterday not in (None, ""):
        delta = _to_float(daily) - _to_float(yesterday)
    return {
        "daily": daily,
        "monthly": monthly,
        "delta": delta,
        "previous": yesterday,
        "source_type": "mes_packaging_output",
    }


def _packaging_output_for_date(db: Session, business_date: date) -> float | None:
    try:
        totals = daily_overview_builder._query_mes_packaging_output_by_date(db, business_date, business_date)
    except Exception:
        return None
    value = totals.get(business_date)
    if value in (None, ""):
        return None
    parsed = _to_float(value)
    return parsed if parsed > 0 else None


def _manual_workshop_source_detail(
    *,
    workshop_name: str,
    start: date,
    end: date,
    row_count: int,
    latest_row_id: int | None,
    unit: str,
) -> dict[str, Any]:
    window_start, _unused = production_business_window(start, workshop_name=workshop_name)
    _unused, window_end = production_business_window(end, workshop_name=workshop_name)
    detail: dict[str, Any] = {
        "source_ref": WorkOrderEntry.__tablename__,
        "business_window": f"{window_start.isoformat()}/{window_end.isoformat()}",
        "unit": unit,
        "row_count": row_count,
        "metric_contract_version": "2026-07-11",
    }
    if row_count > 0 and latest_row_id is not None:
        detail.update(
            {
                "latest_row_id": latest_row_id,
                "trace_id": f"manual-read:{WorkOrderEntry.__tablename__}:{latest_row_id}:{row_count}",
            }
        )
    return detail


def collect_manual_workshop_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    for key, workshop_names in MANUAL_OUTPUT_WORKSHOPS.items():
        daily, daily_pass, daily_count, daily_latest_row_id = _query_manual_mobile_output(
            db,
            start=facts.target_date,
            end=facts.target_date,
            workshop_names=workshop_names,
        )
        monthly, monthly_pass, monthly_count, monthly_latest_row_id = _query_manual_mobile_output(
            db,
            start=month_start,
            end=facts.target_date,
            workshop_names=workshop_names,
        )
        daily_detail = _manual_workshop_source_detail(
            workshop_name=workshop_names[0],
            start=facts.target_date,
            end=facts.target_date,
            row_count=daily_count,
            latest_row_id=daily_latest_row_id,
            unit="吨",
        )
        monthly_detail = _manual_workshop_source_detail(
            workshop_name=workshop_names[0],
            start=month_start,
            end=facts.target_date,
            row_count=monthly_count,
            latest_row_id=monthly_latest_row_id,
            unit="吨",
        )
        _set_value(facts, key, daily, "manual_mobile_coil", **daily_detail)
        _set_value(
            facts,
            MONTHLY_FIELD_BY_DAILY_FIELD[key],
            monthly,
            "manual_mobile_coil",
            **monthly_detail,
        )
        pass_fields = PASS_FIELDS_BY_DAILY_FIELD.get(key)
        if pass_fields is not None:
            _set_value(
                facts,
                pass_fields[0],
                daily_pass,
                "manual_mobile_coil",
                **{**daily_detail, "unit": "道"},
            )
            _set_value(
                facts,
                pass_fields[1],
                monthly_pass,
                "manual_mobile_coil",
                **{**monthly_detail, "unit": "道"},
            )


def _latest_promoted_daily_production_batch(db: Session, target_date: date) -> ImportBatch | None:
    return (
        db.query(ImportBatch)
        .join(ShiftProductionData, ShiftProductionData.import_batch_id == ImportBatch.id)
        .filter(
            ImportBatch.import_type == "daily_production_report",
            ImportBatch.source_type == "daily_production_report_locked",
            ImportBatch.parsed_successfully.is_(True),
            ImportBatch.quality_status != "blocked",
            ShiftProductionData.business_date == target_date,
            ShiftProductionData.data_source == "daily_production_report",
            ShiftProductionData.data_status == "confirmed",
        )
        .order_by(ImportBatch.id.desc())
        .first()
    )


def _imported_production_field(row: Any) -> str | None:
    equipment_code = str(row.equipment_code or "").strip().upper()
    if equipment_code in IMPORTED_PRODUCTION_FIELD_BY_EQUIPMENT:
        return IMPORTED_PRODUCTION_FIELD_BY_EQUIPMENT[equipment_code]

    workshop_code = str(row.workshop_code or "").strip().upper()
    if workshop_code in IMPORTED_PRODUCTION_FIELD_BY_WORKSHOP:
        return IMPORTED_PRODUCTION_FIELD_BY_WORKSHOP[workshop_code]

    project_label = str(row.project_label or "").strip().replace(" ", "")
    workshop_label = str(row.workshop_label or "").strip().replace(" ", "")
    if workshop_code == "JZ" and row.equipment_id is None and project_label == "剪子":
        return "finishing_daily"
    if workshop_code == "JQ" and row.equipment_id is None and workshop_label in {"园区剪切", "剪切"}:
        return "shearing_daily"
    return None


def _production_bucket_key(row: DailyProductionMappingRow) -> tuple[date, int, int | None] | None:
    if row.business_date is None or row.workshop_id is None:
        return None
    try:
        business_date = date.fromisoformat(str(row.business_date))
    except ValueError:
        return None
    return business_date, int(row.workshop_id), int(row.equipment_id) if row.equipment_id is not None else None


def _production_metric_matches(
    rows: list[DailyProductionMappingRow],
    attribute: str,
    promoted_value: Any,
) -> bool:
    values = [getattr(row, attribute) for row in rows if getattr(row, attribute) is not None]
    expected = round(sum(float(value) for value in values), 3) if values else None
    if expected is None:
        return promoted_value is None
    if promoted_value is None:
        return False
    actual = float(promoted_value)
    return math.isfinite(expected) and math.isfinite(actual) and math.isclose(
        expected,
        actual,
        abs_tol=0.001,
    )


def _promoted_report_metric_matches(
    fact: ImportedDailyMetricFact,
    import_row: ImportRow | None,
) -> bool:
    if import_row is None or import_row.batch_id != fact.import_batch_id or import_row.status != "success":
        return False
    mapped = import_row.mapped_data if isinstance(import_row.mapped_data, dict) else {}
    if (
        not daily_production_lineage_is_valid(mapped)
        or str(mapped.get("lineage_hash") or "") != fact.lineage_hash
        or str(mapped.get("business_date") or "") != fact.business_date.isoformat()
        or str(mapped.get("quality_status") or "").strip().lower() not in {"ready", "warning"}
        or fact.metric_contract_version != DAILY_REPORT_FIELD_CONTRACT_VERSION
    ):
        return False
    matches = [
        item
        for item in mapped.get("report_metrics") or []
        if isinstance(item, dict) and str(item.get("field_name") or "") == fact.field_name
    ]
    if len(matches) != 1:
        return False
    metric = matches[0]
    try:
        staged_value = float(metric.get("value"))
        promoted_value = float(fact.metric_value)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(staged_value)
        and math.isfinite(promoted_value)
        and math.isclose(staged_value, promoted_value, rel_tol=0.0, abs_tol=0.000001)
        and str(metric.get("unit") or "") == fact.unit
        and metric.get("source_anchors") == fact.source_anchors
    )


def _report_metric_value(field_name: str, unit: str, value: Any) -> float:
    decimal_value = Decimal(str(value))
    if field_name == "cost_basis_weight":
        return float(decimal_value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    if unit in {"吨", "道"}:
        return float(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if unit in {"kWh/吨", "m³/吨"}:
        return float(decimal_value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return float(decimal_value)


def _report_metric_business_window(field_name: str, business_date: date) -> str:
    start_date = business_date.replace(day=1) if field_name.endswith("_month") else business_date
    window_start, _unused = production_business_window(start_date)
    _unused, window_end = production_business_window(business_date)
    return f"{window_start.isoformat()}/{window_end.isoformat()}"


def _set_promoted_report_metric(
    facts: TemplateDailyFacts,
    fact: ImportedDailyMetricFact,
    *,
    file_name: str,
) -> None:
    source_extra: dict[str, Any] = {
        "source_ref": ImportedDailyMetricFact.__tablename__,
        "metric_fact_id": fact.id,
        "import_batch_id": fact.import_batch_id,
        "import_row_id": fact.import_row_id,
        "business_date": fact.business_date.isoformat(),
        "business_window": _report_metric_business_window(fact.field_name, fact.business_date),
        "unit": fact.unit,
        "file_name": file_name,
        "row_anchors": fact.source_anchors,
        "lineage_hash": fact.lineage_hash,
        "metric_contract_version": DAILY_REPORT_METRIC_CONTRACT_VERSION,
        "field_contract_version": fact.metric_contract_version,
        "trace_id": (
            f"import-read:{ImportedDailyMetricFact.__tablename__}:{fact.id}:"
            f"{fact.field_name}:{fact.lineage_hash[:12]}"
        ),
    }
    existing_source = facts.sources.get(fact.field_name) or {}
    if (
        fact.field_name in {"total_output_daily", "total_output_month", "cost_basis_weight"}
        and existing_source.get("source_type") == "mes_packaging_output"
    ):
        source_extra["replaced_proxy_source"] = {
            key: existing_source.get(key)
            for key in ("source_type", "source_ref", "trace_id", "business_window")
            if existing_source.get(key) is not None
        }
        facts.values.pop(fact.field_name, None)
        facts.sources.pop(fact.field_name, None)
    _set_value(
        facts,
        fact.field_name,
        _report_metric_value(fact.field_name, fact.unit, fact.metric_value),
        "manual_workbook",
        **source_extra,
    )


def _validated_promoted_report_metrics(
    db: Session,
    *,
    batch: ImportBatch,
    target_date: date,
    facts: TemplateDailyFacts,
) -> list[ImportedDailyMetricFact]:
    metric_facts = (
        db.query(ImportedDailyMetricFact)
        .filter(
            ImportedDailyMetricFact.import_batch_id == batch.id,
            ImportedDailyMetricFact.business_date == target_date,
            ImportedDailyMetricFact.source_kind == "daily_production_report",
            ImportedDailyMetricFact.data_status == "confirmed",
        )
        .order_by(ImportedDailyMetricFact.id.asc())
        .all()
    )
    import_rows = {
        row.id: row
        for row in db.query(ImportRow)
        .filter(ImportRow.id.in_({fact.import_row_id for fact in metric_facts}))
        .all()
    } if metric_facts else {}
    accepted: list[ImportedDailyMetricFact] = []
    for fact in metric_facts:
        if _promoted_report_metric_matches(fact, import_rows.get(fact.import_row_id)):
            accepted.append(fact)
            continue
        conflict = {
            "field": fact.field_name,
            "reason": "promoted_metric_lineage_mismatch",
            "import_batch_id": batch.id,
            "metric_fact_id": fact.id,
        }
        if conflict not in facts.conflicts:
            facts.conflicts.append(conflict)
    return accepted


def _previous_promoted_total_output_metric(
    db: Session,
    *,
    target_date: date,
) -> tuple[ImportedDailyMetricFact, ImportBatch] | None:
    result = (
        db.query(ImportedDailyMetricFact, ImportBatch)
        .join(ImportBatch, ImportBatch.id == ImportedDailyMetricFact.import_batch_id)
        .filter(
            ImportedDailyMetricFact.business_date == target_date,
            ImportedDailyMetricFact.field_name == "total_output_daily",
            ImportedDailyMetricFact.source_kind == "daily_production_report",
            ImportedDailyMetricFact.data_status == "confirmed",
            ImportBatch.source_type == "daily_production_report_locked",
            ImportBatch.parsed_successfully.is_(True),
            ImportBatch.quality_status != "blocked",
        )
        .order_by(ImportedDailyMetricFact.id.desc())
        .first()
    )
    if result is None:
        return None
    fact, batch = result
    import_row = db.get(ImportRow, fact.import_row_id)
    return (fact, batch) if _promoted_report_metric_matches(fact, import_row) else None


def collect_imported_daily_production_facts(db: Session, facts: TemplateDailyFacts) -> None:
    required_tables = (
        ImportBatch.__tablename__,
        ImportRow.__tablename__,
        ImportedDailyMetricFact.__tablename__,
        ShiftProductionData.__tablename__,
        Workshop.__tablename__,
        Equipment.__tablename__,
    )
    if not all(_has_table(db, table_name) for table_name in required_tables):
        return
    batch = _latest_promoted_daily_production_batch(db, facts.target_date)
    if batch is None:
        return
    trusted_import_rows = (
        db.query(ImportRow)
        .filter(
            ImportRow.batch_id == batch.id,
            ImportRow.status == "success",
        )
        .order_by(ImportRow.row_number.asc())
        .all()
    )
    trusted_import_row_ids = {
        row.id
        for row in trusted_import_rows
        if isinstance(row.mapped_data, dict)
        and daily_production_lineage_is_valid(row.mapped_data)
        and str(row.mapped_data.get("business_date") or "") == facts.target_date.isoformat()
        and str(row.mapped_data.get("quality_status") or "").strip().lower() in {"ready", "warning"}
    }
    if not trusted_import_row_ids:
        return
    preview = build_daily_production_mapping_preview(
        db,
        batch_id=batch.id,
        import_row_ids=trusted_import_row_ids,
    )

    preview_buckets: dict[tuple[date, int, int | None], list[DailyProductionMappingRow]] = {}
    for row in preview.rows:
        key = _production_bucket_key(row) if row.status == "ready" else None
        if key is not None:
            preview_buckets.setdefault(key, []).append(row)
    promoted_rows = (
        db.query(ShiftProductionData)
        .filter(
            ShiftProductionData.import_batch_id == batch.id,
            ShiftProductionData.business_date == facts.target_date,
            ShiftProductionData.data_source == "daily_production_report",
            ShiftProductionData.data_status == "confirmed",
        )
        .order_by(ShiftProductionData.id.asc())
        .all()
    )
    promoted_by_bucket: dict[tuple[date, int, int | None], list[ShiftProductionData]] = {}
    for promoted in promoted_rows:
        key = (
            promoted.business_date,
            int(promoted.workshop_id),
            int(promoted.equipment_id) if promoted.equipment_id is not None else None,
        )
        promoted_by_bucket.setdefault(key, []).append(promoted)

    accepted_rows: list[DailyProductionMappingRow] = []
    promoted_fact_ids_by_anchor: dict[tuple[int | None, int | None], int] = {}
    mismatched_bucket_count = 0
    for key, rows in preview_buckets.items():
        matching_facts = promoted_by_bucket.get(key) or []
        if len(matching_facts) != 1:
            mismatched_bucket_count += 1
            continue
        promoted = matching_facts[0]
        if not all(
            (
                _production_metric_matches(rows, "daily_input_tons", promoted.input_weight),
                _production_metric_matches(rows, "daily_output_tons", promoted.output_weight),
                _production_metric_matches(rows, "daily_scrap_tons", promoted.scrap_weight),
            )
        ):
            mismatched_bucket_count += 1
            continue
        accepted_rows.extend(rows)
        for row in rows:
            promoted_fact_ids_by_anchor[(row.import_row_id, row.row_index)] = promoted.id
    if mismatched_bucket_count:
        facts.conflicts.append(
            {
                "field": "daily_production_workbook",
                "reason": "promoted_lineage_mismatch",
                "import_batch_id": batch.id,
                "bucket_count": mismatched_bucket_count,
            }
        )

    grouped: dict[str, list[DailyProductionMappingRow]] = {}
    for row in accepted_rows:
        field_name = _imported_production_field(row)
        if field_name is not None:
            grouped.setdefault(field_name, []).append(row)

    for field_name, rows in grouped.items():
        daily_values = [row.daily_output_tons for row in rows if row.daily_output_tons is not None]
        row_anchors = [
            {
                "import_row_id": row.import_row_id,
                "import_row_number": row.import_row_number,
                "workbook_row_index": row.row_index,
            }
            for row in rows
        ]
        workshop_name = next((row.workshop_name for row in rows if row.workshop_name), None)
        daily_start, daily_end = production_business_window(
            facts.target_date,
            workshop_name=workshop_name,
        )
        anchor_token = ",".join(
            f"{row.import_row_id}.{row.row_index}"
            for row in rows
        )
        source_base = {
            "source_ref": ImportRow.__tablename__,
            "import_batch_id": batch.id,
            "file_name": batch.file_name,
            "business_date": facts.target_date.isoformat(),
            "unit": "吨",
            "row_count": len(rows),
            "row_anchors": row_anchors,
            "promoted_fact_ids": sorted(
                {
                    promoted_fact_ids_by_anchor[(row.import_row_id, row.row_index)]
                    for row in rows
                }
            ),
            "metric_contract_version": DAILY_REPORT_FIELD_CONTRACT_VERSION,
        }
        if daily_values:
            _set_value(
                facts,
                field_name,
                sum(float(value) for value in daily_values),
                "manual_workbook",
                **source_base,
                business_window=f"{daily_start.isoformat()}/{daily_end.isoformat()}",
                trace_id=(
                    f"import-read:{ImportRow.__tablename__}:{batch.id}:"
                    f"{field_name}:{anchor_token}"
                ),
            )

    promoted_metrics = _validated_promoted_report_metrics(
        db,
        batch=batch,
        target_date=facts.target_date,
        facts=facts,
    )
    for metric_fact in promoted_metrics:
        _set_promoted_report_metric(facts, metric_fact, file_name=batch.file_name)

    current_total = next(
        (fact for fact in promoted_metrics if fact.field_name == "total_output_daily"),
        None,
    )
    retained_total_source = facts.sources.get("total_output_daily") or {}
    if (
        current_total is not None
        and retained_total_source.get("metric_fact_id") == current_total.id
    ):
        previous = _previous_promoted_total_output_metric(
            db,
            target_date=facts.target_date - timedelta(days=1),
        )
        if previous is not None:
            previous_fact, previous_batch = previous
            current_value = _report_metric_value(
                current_total.field_name,
                current_total.unit,
                current_total.metric_value,
            )
            previous_value = _report_metric_value(
                previous_fact.field_name,
                previous_fact.unit,
                previous_fact.metric_value,
            )
            delta_start, _unused = production_business_window(previous_fact.business_date)
            _unused, delta_end = production_business_window(current_total.business_date)
            _set_value(
                facts,
                "total_output_delta",
                current_value - previous_value,
                "computed",
                source_ref=ImportedDailyMetricFact.__tablename__,
                business_date=facts.target_date.isoformat(),
                business_window=f"{delta_start.isoformat()}/{delta_end.isoformat()}",
                trace_id=(
                    f"computed:imported-total-output-delta:{previous_fact.id}:"
                    f"{current_total.id}"
                ),
                formula="rounded_total_output_daily - rounded_previous_total_output_daily",
                components=[
                    {
                        "metric_fact_id": previous_fact.id,
                        "import_batch_id": previous_batch.id,
                        "business_date": previous_fact.business_date.isoformat(),
                    },
                    {
                        "metric_fact_id": current_total.id,
                        "import_batch_id": batch.id,
                        "business_date": current_total.business_date.isoformat(),
                    },
                ],
                metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
            )


def _latest_promoted_energy_batch(db: Session, target_date: date) -> ImportBatch | None:
    return (
        db.query(ImportBatch)
        .join(EnergyImportRecord, EnergyImportRecord.import_batch_id == ImportBatch.id)
        .filter(
            ImportBatch.import_type == "energy",
            ImportBatch.source_type == "daily_energy_report_locked",
            ImportBatch.parsed_successfully.is_(True),
            ImportBatch.quality_status != "blocked",
            EnergyImportRecord.business_date == target_date,
        )
        .order_by(ImportBatch.id.desc())
        .first()
    )


def _legacy_energy_field_has_promoted_record(
    *,
    field_name: str,
    mapped: dict[str, Any],
    value: float,
    promoted_records: list[EnergyImportRecord],
) -> bool:
    if (
        mapped.get("report_field") != "hot_roll_furnace_gas_m3"
        or field_name not in {"east_furnace_gas_m3", "west_furnace_gas_m3"}
    ):
        return False
    try:
        source_row_no = int(mapped.get("source_row_no"))
    except (TypeError, ValueError):
        return False
    energy_type = str(mapped.get("energy_type") or "").strip().lower()
    workshop_code = str(mapped.get("workshop_code") or "").strip()
    for record in promoted_records:
        try:
            record_value = float(record.energy_value)
        except (TypeError, ValueError):
            continue
        if (
            record.source_row_no == source_row_no
            and record.energy_type == energy_type
            and math.isfinite(record_value)
            and math.isclose(record_value, value, rel_tol=0.0, abs_tol=0.000001)
            and (not workshop_code or record.workshop_code == workshop_code)
        ):
            return True
    return False


def collect_imported_energy_workbook_facts(db: Session, facts: TemplateDailyFacts) -> None:
    required_tables = (ImportBatch.__tablename__, ImportRow.__tablename__, EnergyImportRecord.__tablename__)
    if not all(_has_table(db, table_name) for table_name in required_tables):
        return
    batch = _latest_promoted_energy_batch(db, facts.target_date)
    if batch is None:
        return
    import_rows = (
        db.query(ImportRow)
        .filter(
            ImportRow.batch_id == batch.id,
            ImportRow.status.in_(("success", "skipped")),
        )
        .order_by(ImportRow.row_number.asc())
        .all()
    )
    promoted_records = (
        db.query(EnergyImportRecord)
        .filter(
            EnergyImportRecord.import_batch_id == batch.id,
            EnergyImportRecord.business_date == facts.target_date,
        )
        .all()
    )

    grouped: dict[str, list[tuple[float, ImportRow, dict[str, Any]]]] = {}
    for row in import_rows:
        mapped = row.mapped_data if isinstance(row.mapped_data, dict) else {}
        if str(mapped.get("business_date") or "") != facts.target_date.isoformat():
            continue
        try:
            value = float(mapped.get("energy_value"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        field_name = daily_energy_report_fact_field(
            str(mapped.get("energy_type") or "").strip().lower(),
            str(mapped.get("source_label") or ""),
        )
        if field_name is None:
            continue
        if (
            mapped.get("report_field") != field_name
            and not _legacy_energy_field_has_promoted_record(
                field_name=field_name,
                mapped=mapped,
                value=value,
                promoted_records=promoted_records,
            )
        ):
            continue
        grouped.setdefault(field_name, []).append((value, row, mapped))

    if "cast_2_gas_m3" in grouped or "cast_3_gas_m3" in grouped:
        grouped["cast_roll_gas_m3"] = [
            *grouped.get("cast_2_gas_m3", []),
            *grouped.get("cast_3_gas_m3", []),
        ]
    if "east_furnace_gas_m3" in grouped or "west_furnace_gas_m3" in grouped:
        grouped["hot_roll_furnace_gas_m3"] = [
            *grouped.get("hot_roll_furnace_gas_m3", []),
            *grouped.get("east_furnace_gas_m3", []),
            *grouped.get("west_furnace_gas_m3", []),
        ]

    energy_start, energy_end = production_business_window(facts.target_date)
    energy_business_window = f"{energy_start.isoformat()}/{energy_end.isoformat()}"
    for field_name, values in grouped.items():
        row_anchors = [
            {
                "import_row_id": row.id,
                "import_row_number": row.row_number,
                "workbook_row_number": mapped.get("source_row_no"),
                "source_file": mapped.get("source_file"),
                "source_sheet": mapped.get("source_sheet"),
                "source_label": mapped.get("source_label"),
            }
            for _value, row, mapped in values
        ]
        anchor_token = ",".join(str(row.id) for _value, row, _mapped in values)
        _set_value(
            facts,
            field_name,
            sum(value for value, _row, _mapped in values),
            "manual_workbook",
            source_ref=ImportRow.__tablename__,
            import_batch_id=batch.id,
            file_name=batch.file_name,
            business_date=facts.target_date.isoformat(),
            business_window=energy_business_window,
            unit=("度" if field_name.endswith("electricity_kwh") else "m³"),
            row_count=len(values),
            row_anchors=row_anchors,
            metric_contract_version=DAILY_REPORT_METRIC_CONTRACT_VERSION,
            field_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
            trace_id=(
                f"import-read:{ImportRow.__tablename__}:{batch.id}:"
                f"{field_name}:{anchor_token}"
            ),
        )

    electricity = facts.values.get("total_electricity_kwh")
    gas = facts.values.get("total_gas_m3")
    if electricity is None and gas is None:
        return
    component_fields = [
        field_name
        for field_name in ("total_electricity_kwh", "total_gas_m3")
        if facts.values.get(field_name) is not None
    ]
    component_source_keys = (
        "source_type",
        "source_ref",
        "trace_id",
        "business_date",
        "business_window",
        "import_batch_id",
        "row_anchors",
        "metric_contract_version",
    )
    component_sources: dict[str, dict[str, Any]] = {}
    for field_name in component_fields:
        source = facts.sources.get(field_name) or {}
        component_sources[field_name] = {
            key: source.get(key)
            for key in component_source_keys
            if source.get(key) is not None
        }
    electricity_cost_raw = None
    gas_cost_raw = None
    electricity_cost = None
    gas_cost = None
    if electricity is not None:
        electricity_cost_raw = (
            _to_float(electricity) * daily_overview_builder.DEFAULT_ELECTRICITY_PRICE / 10000
        )
        electricity_cost = round(electricity_cost_raw, 2)
        _set_value(
            facts,
            "electricity_cost_10k",
            electricity_cost,
            "computed",
            source_ref="template_daily_facts",
            business_date=facts.target_date.isoformat(),
            business_window=energy_business_window,
            trace_id=f"computed:energy-cost:electricity:{facts.target_date.isoformat()}",
            formula="total_electricity_kwh * electricity_unit_price / 10000",
            components=["total_electricity_kwh"],
            component_sources={"total_electricity_kwh": component_sources["total_electricity_kwh"]},
            unit_prices={"electricity": daily_overview_builder.DEFAULT_ELECTRICITY_PRICE},
            metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
        )
    if gas is not None:
        gas_cost_raw = _to_float(gas) * daily_overview_builder.DEFAULT_GAS_PRICE / 10000
        gas_cost = round(gas_cost_raw, 2)
        _set_value(
            facts,
            "gas_cost_10k",
            gas_cost,
            "computed",
            source_ref="template_daily_facts",
            business_date=facts.target_date.isoformat(),
            business_window=energy_business_window,
            trace_id=f"computed:energy-cost:gas:{facts.target_date.isoformat()}",
            formula="total_gas_m3 * gas_unit_price / 10000",
            components=["total_gas_m3"],
            component_sources={"total_gas_m3": component_sources["total_gas_m3"]},
            unit_prices={"gas": daily_overview_builder.DEFAULT_GAS_PRICE},
            metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
        )
    if electricity_cost_raw is None or gas_cost_raw is None:
        return
    electricity_source = facts.sources.get("total_electricity_kwh") or {}
    gas_source = facts.sources.get("total_gas_m3") or {}
    same_promoted_workbook_batch = (
        electricity_source.get("source_type") == "manual_workbook"
        and gas_source.get("source_type") == "manual_workbook"
        and electricity_source.get("import_batch_id") == batch.id
        and gas_source.get("import_batch_id") == batch.id
    )
    if not same_promoted_workbook_batch:
        if facts.values.get("total_cost_10k") is None:
            conflict = {
                "field": "total_cost_10k",
                "reason": "mixed_energy_source_batch",
                "component_fields": ["total_electricity_kwh", "total_gas_m3"],
            }
            if conflict not in facts.conflicts:
                facts.conflicts.append(conflict)
        return
    total_cost_raw = electricity_cost_raw + gas_cost_raw
    total_cost = round(total_cost_raw, 2)
    total_cost_trace_id = f"computed:energy-cost:total:{batch.id}:{facts.target_date.isoformat()}"
    _set_value(
        facts,
        "total_cost_10k",
        total_cost,
        "computed",
        source_ref="template_daily_facts",
        import_batch_id=batch.id,
        business_date=facts.target_date.isoformat(),
        business_window=energy_business_window,
        trace_id=total_cost_trace_id,
        formula="electricity_cost_10k + gas_cost_10k",
        components=["total_electricity_kwh", "total_gas_m3"],
        component_sources=component_sources,
        unit_prices={
            "electricity": daily_overview_builder.DEFAULT_ELECTRICITY_PRICE,
            "gas": daily_overview_builder.DEFAULT_GAS_PRICE,
        },
        metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
    )
    basis_weight = facts.values.get("cost_basis_weight")
    if basis_weight is not None and _to_float(basis_weight) > 0:
        retained_total_source = facts.sources.get("total_cost_10k") or {}
        if retained_total_source.get("trace_id") != total_cost_trace_id:
            conflict = {
                "field": "cost_per_ton",
                "reason": "total_cost_source_rejected_workbook_value",
                "component_fields": ["total_cost_10k", "cost_basis_weight"],
            }
            if conflict not in facts.conflicts:
                facts.conflicts.append(conflict)
            return
        basis_source = facts.sources.get("cost_basis_weight") or {}
        cost_per_ton_component_sources = {
            "total_electricity_kwh": component_sources["total_electricity_kwh"],
            "total_gas_m3": component_sources["total_gas_m3"],
            "cost_basis_weight": {
                key: basis_source.get(key)
                for key in component_source_keys
                if basis_source.get(key) is not None
            },
        }
        _set_value(
            facts,
            "cost_per_ton",
            round(total_cost_raw * 10000 / _to_float(basis_weight), 0),
            "computed",
            source_ref="template_daily_facts",
            import_batch_id=batch.id,
            business_date=facts.target_date.isoformat(),
            business_window=energy_business_window,
            trace_id=f"computed:energy-cost:per-ton:{batch.id}:{facts.target_date.isoformat()}",
            formula=(
                "(total_electricity_kwh * electricity_unit_price + "
                "total_gas_m3 * gas_unit_price) / cost_basis_weight"
            ),
            components=["total_electricity_kwh", "total_gas_m3", "cost_basis_weight"],
            component_sources=cost_per_ton_component_sources,
            unit_prices={
                "electricity": daily_overview_builder.DEFAULT_ELECTRICITY_PRICE,
                "gas": daily_overview_builder.DEFAULT_GAS_PRICE,
            },
            unrounded_total_cost_10k=round(total_cost_raw, 6),
            metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
        )


def collect_mes_material_workshop_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    for key, tokens in MES_MATERIAL_OUTPUT_WORKSHOPS.items():
        daily, daily_count, daily_latest_row_id = _query_mes_material_output(
            db,
            start=facts.target_date,
            end=facts.target_date,
            tokens=tokens,
        )
        monthly, monthly_count, monthly_latest_row_id = _query_mes_material_output(
            db,
            start=month_start,
            end=facts.target_date,
            tokens=tokens,
        )
        daily_start, daily_end = production_business_window(facts.target_date, workshop_name=tokens[0])
        daily_source_detail = {
            "source_ref": "mes_material_records",
            "source_table": "MES_Material",
            "business_window": f"{daily_start.isoformat()}/{daily_end.isoformat()}",
            "unit": "吨",
            "row_count": daily_count,
            "metric_contract_version": "2026-07-11",
        }
        if daily_count > 0 and daily_latest_row_id is not None:
            daily_source_detail["latest_row_id"] = daily_latest_row_id
            daily_source_detail["trace_id"] = (
                f"projection-read:mes_material_records:{daily_latest_row_id}:{daily_count}"
            )
        _set_value(facts, key, daily, "mes_material_records", **daily_source_detail)
        month_start_at, _unused = production_business_window(month_start, workshop_name=tokens[0])
        _unused, month_end_at = production_business_window(facts.target_date, workshop_name=tokens[0])
        monthly_source_detail = {
            "source_ref": "mes_material_records",
            "source_table": "MES_Material",
            "business_window": f"{month_start_at.isoformat()}/{month_end_at.isoformat()}",
            "unit": "吨",
            "row_count": monthly_count,
            "metric_contract_version": "2026-07-11",
        }
        if monthly_count > 0 and monthly_latest_row_id is not None:
            monthly_source_detail["latest_row_id"] = monthly_latest_row_id
            monthly_source_detail["trace_id"] = (
                f"projection-read:mes_material_records:{monthly_latest_row_id}:{monthly_count}"
            )
        _set_value(
            facts,
            MONTHLY_FIELD_BY_DAILY_FIELD[key],
            monthly,
            "mes_material_records",
            **monthly_source_detail,
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
        daily, daily_pass, daily_count, daily_latest_row_id = _bucketed_mes_output(
            daily_rows,
            buckets,
            claimed_source_ids=claimed_daily,
        )
        monthly, monthly_pass, monthly_count, monthly_latest_row_id = _bucketed_mes_output(
            month_rows,
            buckets,
            claimed_source_ids=claimed_month,
        )
        daily_start, daily_end = production_business_window(facts.target_date)
        daily_detail = _mes_workshop_source_detail(
            row_count=daily_count,
            latest_row_id=daily_latest_row_id,
            window_start=daily_start,
            window_end=daily_end,
        )
        month_start_at, _unused = production_business_window(month_start)
        _unused, month_end_at = production_business_window(facts.target_date)
        monthly_detail = _mes_workshop_source_detail(
            row_count=monthly_count,
            latest_row_id=monthly_latest_row_id,
            window_start=month_start_at,
            window_end=month_end_at,
        )
        _set_value(facts, key, daily, "mes_workshop_process_records", **daily_detail)
        _set_value(
            facts,
            MONTHLY_FIELD_BY_DAILY_FIELD[key],
            monthly,
            "mes_workshop_process_records",
            **monthly_detail,
        )
        _set_value(facts, key.replace("_daily", "_pass_daily"), daily_pass, "computed")
        _set_value(facts, key.replace("_daily", "_pass_month"), monthly_pass, "computed")


def collect_workshop_rollup_facts(facts: TemplateDailyFacts) -> None:
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


def _collect_optional_workbook_facts(
    db: Session,
    facts: TemplateDailyFacts,
    collector: Callable[[Session, TemplateDailyFacts], None],
    *,
    source_name: str,
) -> None:
    candidate = copy.deepcopy(facts)
    try:
        transaction = db.begin_nested() if callable(getattr(db, "begin_nested", None)) else nullcontext()
        with transaction:
            collector(db, candidate)
    except (OperationalError, ProgrammingError) as exc:
        conflict = {
            "field": source_name,
            "reason": "optional_source_unavailable",
            "error_type": type(exc).__name__,
        }
        if conflict not in facts.conflicts:
            facts.conflicts.append(conflict)
        return
    facts.values = candidate.values
    facts.sources = candidate.sources
    facts.missing_fields = candidate.missing_fields
    facts.conflicts = candidate.conflicts


def collect_template_daily_facts(
    db: Session,
    *,
    target_date: date,
    wip_date: date | None = None,
    required_fields: tuple[str, ...],
    allow_datahub_final_reference: bool = True,
) -> TemplateDailyFacts:
    effective_wip_date = wip_date or (target_date + timedelta(days=1))
    facts = TemplateDailyFacts(target_date=target_date, wip_date=effective_wip_date)
    _set_value(facts, "report_date", target_date, "runtime_target_date")

    collect_opening_facts(db, facts, wip_date=effective_wip_date)
    collect_manual_workshop_facts(db, facts)
    _copy_owner_values(facts, _owner_daily_payload_values(db, target_date=target_date), required_fields)
    collect_owner_rollup_facts(db, facts)
    _collect_optional_workbook_facts(
        db,
        facts,
        collect_imported_daily_production_facts,
        source_name="daily_production_workbook",
    )
    _collect_optional_workbook_facts(
        db,
        facts,
        collect_imported_energy_workbook_facts,
        source_name="daily_energy_workbook",
    )
    collect_workshop_rollup_facts(facts)
    collect_recovery_and_overhaul_facts(db, facts)
    collect_quality_yield_facts(db, facts)
    collect_yesterday_comparison_facts(db, facts)
    if allow_datahub_final_reference:
        collect_datahub_final_daily_report_facts(db, facts)

    facts.missing_fields = [key for key in required_fields if facts.values.get(key) is None]
    return facts
