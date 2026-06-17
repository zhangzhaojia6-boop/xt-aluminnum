from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.master import Workshop
from app.models.mes import MesWorkshopProcessRecord
from app.models.production import OverhaulDaily, RecoveryDaily, WorkOrderEntry
from app.models.quality import QualityYieldDaily
from app.models.reports import DailyReport
from app.services.report import daily_overview_builder
from app.services.report._utils import _to_float
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


SUBMITTED_STATUSES = ("submitted", "verified", "approved")

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

MES_REPORT_PROCESS_MAPPING = {
    "cold_1650_daily": {"include": ("1650",), "exclude": ("1850", "2050", "精整", "拉矫", "剪切", "退火")},
    "cold_1850_daily": {"include": ("1850",), "exclude": ("1650", "2050", "精整", "拉矫", "剪切", "退火")},
    "cold_2050_daily": {"include": ("2050",), "exclude": ("1650", "1850", "精整", "拉矫", "剪切", "退火")},
    "online_anneal_daily": {"include": ("在线退火", "退火"), "exclude": ()},
    "straightening_daily": {"include": ("拉矫",), "exclude": ()},
    "finishing_daily": {"include": ("精整",), "exclude": ()},
    "shearing_daily": {"include": ("剪切",), "exclude": ()},
    "coating_daily": {"include": ("彩涂",), "exclude": ()},
}

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


@dataclass
class TemplateDailyFacts:
    target_date: date
    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "values": self.values,
            "sources": self.sources,
            "missing_fields": self.missing_fields,
            "conflicts": self.conflicts,
        }


def _source(source_type: str, **extra: Any) -> dict[str, Any]:
    return {"source_type": source_type, **extra}


def _has_table(db: Session, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except Exception:
        return True


def _set_value(facts: TemplateDailyFacts, key: str, value: Any, source_type: str, **source_extra: Any) -> None:
    if value is None or value == "":
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
    for row in rows:
        source_key = row.source_id or str(row.id)
        if source_key in claimed_source_ids:
            continue
        text = _row_text(row)
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


def collect_opening_facts(db: Session, facts: TemplateDailyFacts) -> None:
    try:
        overview = daily_overview_builder.build_daily_production_overview(db, target_date=facts.target_date)
    except Exception as exc:
        facts.conflicts.append({"field": "daily_overview", "reason": type(exc).__name__})
        return

    plant_output = dict(overview.get("plant_output") or {})
    contracts = dict(overview.get("contracts") or {})
    yield_rates = dict(overview.get("yield_rates") or {})
    energy = dict(overview.get("energy") or {})
    cost = dict(overview.get("cost") or {})
    wip_distribution = list(overview.get("wip_distribution") or [])

    _set_value(facts, "total_output_daily", plant_output.get("daily_output"), "mes_packaging_output")
    _set_value(facts, "total_output_month", plant_output.get("monthly_output"), "mes_packaging_output")
    _set_value(
        facts,
        "total_output_delta",
        _to_float(plant_output.get("daily_output")) - _to_float(plant_output.get("yesterday_output")),
        "mes_packaging_output",
    )
    _set_value(facts, "finished_inbound_daily", plant_output.get("daily_output"), "mes_packaging_output")
    _set_value(facts, "finished_inbound_month", plant_output.get("monthly_output"), "mes_packaging_output")

    wip_total = sum(_to_float(row.get("total_weight")) for row in wip_distribution)
    if wip_total > 0:
        _set_value(facts, "wip_total", round(wip_total, 2), "mes_wip_distribution")

    _set_value(facts, "daily_contract_weight", contracts.get("daily_new"), "contract_projection")
    _set_value(facts, "remaining_contract_weight", contracts.get("remaining"), "contract_projection")
    _set_value(facts, "remaining_contract_delta", contracts.get("remaining_delta"), "contract_projection")
    _set_value(facts, "daily_yield_rate", yield_rates.get("owner_daily") or yield_rates.get("daily"), "yield_projection")
    _set_value(facts, "daily_yield_delta", yield_rates.get("daily_delta"), "yield_projection")
    _set_value(facts, "monthly_yield_rate", yield_rates.get("monthly"), "yield_projection")
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


def collect_mes_workshop_facts(db: Session, facts: TemplateDailyFacts) -> None:
    month_start = facts.target_date.replace(day=1)
    daily_rows = _mes_rows(db, start=facts.target_date, end=facts.target_date)
    month_rows = _mes_rows(db, start=month_start, end=facts.target_date)
    claimed_daily: set[str] = set()
    claimed_month: set[str] = set()

    for key, mapping in MES_REPORT_PROCESS_MAPPING.items():
        daily, daily_pass, _daily_count = _mapped_mes_output(daily_rows, mapping, claimed_source_ids=claimed_daily)
        monthly, monthly_pass, _monthly_count = _mapped_mes_output(month_rows, mapping, claimed_source_ids=claimed_month)
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


def collect_template_daily_facts(
    db: Session,
    *,
    target_date: date,
    required_fields: tuple[str, ...],
) -> TemplateDailyFacts:
    facts = TemplateDailyFacts(target_date=target_date)
    _set_value(facts, "report_date", target_date, "runtime_target_date")

    collect_opening_facts(db, facts)
    _copy_owner_values(facts, _owner_daily_payload_values(db, target_date=target_date), required_fields)
    collect_owner_rollup_facts(db, facts)
    collect_manual_workshop_facts(db, facts)
    collect_mes_workshop_facts(db, facts)
    collect_recovery_and_overhaul_facts(db, facts)
    collect_quality_yield_facts(db, facts)
    collect_yesterday_comparison_facts(db, facts)

    facts.missing_fields = [key for key in required_fields if facts.values.get(key) is None]
    return facts
