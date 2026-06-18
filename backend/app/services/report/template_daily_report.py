from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.master import Workshop
from app.models.mes import MesWorkshopProcessRecord
from app.models.production import OverhaulDaily, RecoveryDaily, WorkOrderEntry
from app.models.reports import DailyReport
from app.services.report import daily_overview_builder
from app.services.report._utils import _to_float
from app.services.report.template_daily_fact_sources import collect_template_daily_facts


SUBMITTED_STATUSES = ("submitted", "verified", "approved")
TEMPLATE_REPORT_KEY = "template_daily_report"

MANUAL_OUTPUT_WORKSHOPS = {
    "hot_roll_daily": ("热轧",),
    "foundry_daily": ("铸锭", "熔铸", "熔炼"),
    "cast_2_daily": ("铸二", "铸轧二"),
    "cast_3_daily": ("铸三", "铸轧三"),
}

MES_OUTPUT_WORKSHOPS = {
    "cold_1650_daily": ("1650",),
    "cold_1850_daily": ("1850",),
    "cold_2050_daily": ("2050",),
    "online_anneal_daily": ("在线退火", "退火"),
    "straightening_daily": ("拉矫",),
    "finishing_daily": ("精整",),
    "shearing_daily": ("剪切",),
    "coating_daily": ("彩涂",),
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
}

REQUIRED_FIELDS = (
    "report_date",
    "total_output_daily",
    "outsourced_daily",
    "total_output_delta",
    "total_output_month",
    "outsourced_month",
    "cast_roll_active_lines",
    "cast_roll_daily",
    "cast_roll_month",
    "foundry_daily",
    "foundry_month",
    "hot_roll_daily",
    "hot_roll_month",
    "cold_1650_daily",
    "cold_1650_month",
    "cold_1650_pass_daily",
    "cold_1650_pass_month",
    "cold_1850_daily",
    "cold_1850_month",
    "cold_1850_pass_daily",
    "cold_1850_pass_month",
    "cold_2050_daily",
    "cold_2050_month",
    "cold_2050_pass_daily",
    "cold_2050_pass_month",
    "rolling_daily",
    "rolling_month",
    "rolling_pass_daily",
    "rolling_pass_month",
    "online_anneal_daily",
    "online_anneal_month",
    "straightening_daily",
    "straightening_month",
    "finishing_daily",
    "finishing_month",
    "shearing_daily",
    "shearing_month",
    "coating_daily",
    "coating_month",
    "recovery_daily",
    "recovery_month",
    "roller_grind_daily",
    "roller_grind_month",
    "wip_total",
    "wip_1650_2050_cold",
    "wip_1850_cold",
    "wip_milling",
    "wip_anneal_total",
    "wip_new_north",
    "wip_new_south",
    "wip_park_anneal",
    "wip_finishing_total",
    "wip_straightening",
    "wip_finishing",
    "wip_park_finishing",
    "wip_hot_plate_shearing",
    "wip_coating",
    "total_electricity_kwh",
    "subitem_electricity_kwh",
    "cast_roll_gas_m3",
    "cast_2_gas_m3",
    "cast_3_gas_m3",
    "smelting_gas_m3",
    "recovery_gas_m3",
    "hot_roll_furnace_gas_m3",
    "east_furnace_gas_m3",
    "west_furnace_gas_m3",
    "hot_roll_boiler_gas_m3",
    "anneal_gas_m3",
    "straightening_boiler_gas_m3",
    "new_north_gas_m3",
    "new_south_gas_m3",
    "coating_gas_m3",
    "canteen_gas_m3",
    "total_gas_m3",
    "cast_roll_electricity_per_ton_daily",
    "cast_roll_electricity_per_ton_month",
    "cast_roll_gas_per_ton_daily",
    "cast_roll_gas_per_ton_month",
    "foundry_electricity_per_ton_daily",
    "foundry_electricity_per_ton_month",
    "foundry_gas_per_ton_daily",
    "foundry_gas_per_ton_month",
    "hot_roll_electricity_per_ton_daily",
    "hot_roll_electricity_per_ton_month",
    "hot_roll_gas_per_ton_daily",
    "hot_roll_gas_per_ton_month",
    "cold_1650_electricity_per_ton_daily",
    "cold_1650_electricity_per_ton_month",
    "cold_1850_electricity_per_ton_daily",
    "cold_1850_electricity_per_ton_month",
    "cold_2050_electricity_per_ton_daily",
    "cold_2050_electricity_per_ton_month",
    "online_anneal_electricity_per_ton_daily",
    "online_anneal_electricity_per_ton_month",
    "straightening_electricity_per_ton_daily",
    "straightening_electricity_per_ton_month",
    "finishing_electricity_per_ton_daily",
    "finishing_electricity_per_ton_month",
    "shearing_electricity_per_ton_daily",
    "shearing_electricity_per_ton_month",
    "coating_electricity_per_ton_daily",
    "coating_electricity_per_ton_month",
    "coating_gas_per_ton_daily",
    "coating_gas_per_ton_month",
    "finished_inbound_daily",
    "consignment_weight",
    "finished_inbound_month",
    "daily_contract_weight",
    "daily_hot_roll_contract_weight",
    "cold_roll_input_daily",
    "cold_2050_input_daily",
    "cold_1850_input_daily",
    "outsourced_input_daily",
    "medium_plate_input_daily",
    "remaining_contract_weight",
    "remaining_contract_delta",
    "daily_yield_rate",
    "daily_yield_delta",
    "hot_roll_yield_rate",
    "hot_roll_yield_delta",
    "monthly_yield_rate",
    "cast_roll_yield_rate",
    "plate_coil_yield_rate",
    "hot_roll_monthly_yield_rate",
    "electricity_cost_10k",
    "gas_cost_10k",
    "total_cost_10k",
    "cost_basis_weight",
    "cost_per_ton",
)


def _source(source_type: str, **extra: Any) -> dict[str, Any]:
    return {"source_type": source_type, **extra}


def _has_table(db: Session, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except Exception:
        return True


def _set_value(
    values: dict[str, Any],
    sources: dict[str, Any],
    key: str,
    value: Any,
    source_type: str,
    **source_extra: Any,
) -> None:
    if value is None:
        return
    if isinstance(value, float):
        value = round(value, 3)
    values[key] = value
    sources[key] = _source(source_type, **source_extra)


def _round2(value: Any) -> float | None:
    if value is None:
        return None
    return round(_to_float(value), 2)


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _fmt_int(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(int(round(_to_float(value))))


def _fmt_0_or_1(value: Any) -> str:
    if _is_missing(value):
        return ""
    number = round(_to_float(value), 1)
    if number == int(number):
        return str(int(number))
    return f"{number:.1f}"


def _fmt_1(value: Any) -> str:
    if _is_missing(value):
        return ""
    return f"{_to_float(value):.1f}"


def _fmt_2(value: Any) -> str:
    if _is_missing(value):
        return ""
    return f"{_to_float(value):.2f}"


def _fmt_3(value: Any) -> str:
    if _is_missing(value):
        return ""
    return f"{_to_float(value):.3f}"


def _delta_text(value: Any, unit: str = "") -> str:
    if _is_missing(value):
        return ""
    delta = _to_float(value)
    arrow = "↑" if delta >= 0 else "↓"
    magnitude = abs(delta)
    if unit == "%":
        return f"{arrow}{magnitude:.2f}%"
    return f"{arrow}{_fmt_0_or_1(magnitude)}{unit}"


def _month_day(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, date):
        return f"{value.month}月{value.day}日"
    parsed = date.fromisoformat(str(value))
    return f"{parsed.month}月{parsed.day}日"


def _matches_any(value: Any, tokens: tuple[str, ...]) -> bool:
    text = str(value or "")
    return any(token and token in text for token in tokens)


def _output_weight_tons(row: MesWorkshopProcessRecord) -> float:
    direct = _to_float(row.output_weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.output_weight_kg) / 1000


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


def _query_mes_output(
    db: Session,
    *,
    start: date,
    end: date,
    tokens: tuple[str, ...],
) -> tuple[float | None, int]:
    if not _has_table(db, MesWorkshopProcessRecord.__tablename__):
        return None, 0
    rows = (
        db.query(MesWorkshopProcessRecord)
        .filter(
            MesWorkshopProcessRecord.business_date >= start,
            MesWorkshopProcessRecord.business_date <= end,
        )
        .all()
    )
    total = 0.0
    count = 0
    for row in rows:
        if not (
            _matches_any(row.workshop_name, tokens)
            or _matches_any(row.process_name, tokens)
            or _matches_any(row.device_name, tokens)
        ):
            continue
        total += _output_weight_tons(row)
        count += 1
    if count:
        return round(total, 3), count
    return (0.0, 0) if rows else (None, 0)


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


def _copy_owner_values(values: dict[str, Any], sources: dict[str, Any], owner_payload: dict[str, Any]) -> None:
    for key in REQUIRED_FIELDS:
        for source_key in (key, *OWNER_FIELD_ALIASES.get(key, ())):
            if source_key in owner_payload:
                _set_value(values, sources, key, _to_float(owner_payload[source_key]), "owner_daily", field=source_key)
                break


def _copy_overview_values(values: dict[str, Any], sources: dict[str, Any], overview: dict[str, Any]) -> None:
    plant_output = dict(overview.get("plant_output") or {})
    contracts = dict(overview.get("contracts") or {})
    yield_rates = dict(overview.get("yield_rates") or {})
    energy = dict(overview.get("energy") or {})
    cost = dict(overview.get("cost") or {})
    wip_distribution = list(overview.get("wip_distribution") or [])

    _set_value(values, sources, "total_output_daily", plant_output.get("daily_output"), "mes_packaging_output")
    _set_value(values, sources, "total_output_month", plant_output.get("monthly_output"), "mes_packaging_output")
    _set_value(
        values,
        sources,
        "total_output_delta",
        _to_float(plant_output.get("daily_output")) - _to_float(plant_output.get("yesterday_output")),
        "mes_packaging_output",
    )
    _set_value(
        values,
        sources,
        "finished_inbound_daily",
        plant_output.get("finished_inbound_output"),
        plant_output.get("finished_inbound_source") or "finished_inbound_output",
    )
    _set_value(
        values,
        sources,
        "finished_inbound_month",
        plant_output.get("finished_inbound_monthly_output"),
        plant_output.get("finished_inbound_source") or "finished_inbound_output",
    )

    wip_total = sum(_to_float(row.get("total_weight")) for row in wip_distribution)
    if wip_total > 0:
        _set_value(values, sources, "wip_total", round(wip_total, 2), "mes_wip_distribution")

    _set_value(values, sources, "daily_contract_weight", contracts.get("daily_new"), "contract_projection")
    _set_value(values, sources, "remaining_contract_weight", contracts.get("remaining"), "contract_projection")
    _set_value(values, sources, "remaining_contract_delta", contracts.get("remaining_delta"), "contract_projection")
    _set_value(values, sources, "daily_yield_rate", yield_rates.get("owner_daily") or yield_rates.get("daily"), "yield_projection")
    _set_value(values, sources, "daily_yield_delta", yield_rates.get("daily_delta"), "yield_projection")
    _set_value(values, sources, "monthly_yield_rate", yield_rates.get("monthly"), "yield_projection")
    _set_value(values, sources, "total_electricity_kwh", energy.get("total_electricity"), "owner_or_energy_summary")
    _set_value(values, sources, "total_gas_m3", energy.get("total_gas"), "owner_or_energy_summary")
    _set_value(values, sources, "electricity_cost_10k", cost.get("electricity_cost"), "energy_cost")
    _set_value(values, sources, "gas_cost_10k", cost.get("gas_cost"), "energy_cost")
    _set_value(values, sources, "total_cost_10k", cost.get("total"), "energy_cost")
    _set_value(values, sources, "cost_per_ton", cost.get("cost_per_ton"), "energy_cost")
    _set_value(values, sources, "cost_basis_weight", cost.get("basis_weight"), "energy_cost")


def _copy_workshop_outputs(db: Session, *, target_date: date, values: dict[str, Any], sources: dict[str, Any]) -> None:
    month_start = target_date.replace(day=1)
    pass_counts: dict[str, int] = {}
    for key, tokens in MANUAL_OUTPUT_WORKSHOPS.items():
        daily, daily_pass = _query_manual_mobile_output(db, start=target_date, end=target_date, tokens=tokens)
        monthly, monthly_pass = _query_manual_mobile_output(db, start=month_start, end=target_date, tokens=tokens)
        _set_value(values, sources, key, daily, "manual_mobile_coil")
        _set_value(values, sources, MONTHLY_FIELD_BY_DAILY_FIELD[key], monthly, "manual_mobile_coil")
        pass_counts[key] = daily_pass
        pass_counts[MONTHLY_FIELD_BY_DAILY_FIELD[key]] = monthly_pass

    for key, tokens in MES_OUTPUT_WORKSHOPS.items():
        daily, daily_pass = _query_mes_output(db, start=target_date, end=target_date, tokens=tokens)
        monthly, monthly_pass = _query_mes_output(db, start=month_start, end=target_date, tokens=tokens)
        _set_value(values, sources, key, daily, "mes_workshop_process_records")
        _set_value(values, sources, MONTHLY_FIELD_BY_DAILY_FIELD[key], monthly, "mes_workshop_process_records")
        pass_counts[key] = daily_pass
        pass_counts[MONTHLY_FIELD_BY_DAILY_FIELD[key]] = monthly_pass

    cast_2 = values.get("cast_2_daily")
    cast_3 = values.get("cast_3_daily")
    if cast_2 is not None or cast_3 is not None:
        _set_value(values, sources, "cast_roll_daily", _to_float(cast_2) + _to_float(cast_3), "manual_mobile_coil")
    cast_2_month = values.get("cast_2_month")
    cast_3_month = values.get("cast_3_month")
    if cast_2_month is not None or cast_3_month is not None:
        _set_value(values, sources, "cast_roll_month", _to_float(cast_2_month) + _to_float(cast_3_month), "manual_mobile_coil")

    rolling_keys = ("cold_1650", "cold_1850", "cold_2050")
    if any(values.get(f"{item}_daily") is not None for item in rolling_keys):
        _set_value(
            values,
            sources,
            "rolling_daily",
            sum(_to_float(values.get(f"{item}_daily")) for item in rolling_keys),
            "computed",
        )
    if any(values.get(f"{item}_month") is not None for item in rolling_keys):
        _set_value(
            values,
            sources,
            "rolling_month",
            sum(_to_float(values.get(f"{item}_month")) for item in rolling_keys),
            "computed",
        )

    for prefix in rolling_keys:
        _set_value(values, sources, f"{prefix}_pass_daily", pass_counts.get(f"{prefix}_daily"), "computed")
        _set_value(values, sources, f"{prefix}_pass_month", pass_counts.get(f"{prefix}_month"), "computed")
    if any(values.get(f"{item}_pass_daily") is not None for item in rolling_keys):
        _set_value(
            values,
            sources,
            "rolling_pass_daily",
            sum(_to_float(values.get(f"{item}_pass_daily")) for item in rolling_keys),
            "computed",
        )
    if any(values.get(f"{item}_pass_month") is not None for item in rolling_keys):
        _set_value(
            values,
            sources,
            "rolling_pass_month",
            sum(_to_float(values.get(f"{item}_pass_month")) for item in rolling_keys),
            "computed",
        )


def _copy_recovery_and_overhaul(db: Session, *, target_date: date, values: dict[str, Any], sources: dict[str, Any]) -> None:
    month_start = target_date.replace(day=1)
    try:
        if _has_table(db, RecoveryDaily.__tablename__):
            row = db.query(RecoveryDaily).filter(RecoveryDaily.business_date == target_date).one_or_none()
            monthly = (
                db.query(func.sum(RecoveryDaily.recovery_output_tons))
                .filter(RecoveryDaily.business_date >= month_start, RecoveryDaily.business_date <= target_date)
                .scalar()
            )
            if row is not None:
                _set_value(values, sources, "recovery_daily", row.recovery_output_tons, "recovery_daily")
            _set_value(values, sources, "recovery_month", monthly, "recovery_daily")
        if _has_table(db, OverhaulDaily.__tablename__):
            row = db.query(OverhaulDaily).filter(OverhaulDaily.business_date == target_date).one_or_none()
            monthly = (
                db.query(func.sum(OverhaulDaily.roller_grind_count))
                .filter(OverhaulDaily.business_date >= month_start, OverhaulDaily.business_date <= target_date)
                .scalar()
            )
            if row is not None:
                _set_value(values, sources, "roller_grind_daily", row.roller_grind_count, "overhaul_daily")
            _set_value(values, sources, "roller_grind_month", monthly, "overhaul_daily")
    except (OperationalError, ProgrammingError):
        return


def build_template_daily_report_facts(
    db: Session,
    *,
    target_date: date,
    wip_date: date | None = None,
) -> dict[str, Any]:
    return collect_template_daily_facts(
        db,
        target_date=target_date,
        wip_date=wip_date,
        required_fields=REQUIRED_FIELDS,
    ).as_dict()


def validate_template_daily_report_facts(facts: dict[str, Any]) -> dict[str, Any]:
    values = dict(facts.get("values") or {})
    declared_missing = [str(item) for item in facts.get("missing_fields") or []]
    missing = list(dict.fromkeys([*declared_missing, *[key for key in REQUIRED_FIELDS if values.get(key) is None]]))
    return {
        "status": "ready",
        "text": render_template_daily_report(facts),
        "missing_fields": missing,
        "conflicts": list(facts.get("conflicts") or []),
    }


def render_template_daily_report(facts: dict[str, Any]) -> str:
    class BlankValues(dict):
        def __missing__(self, key: str) -> None:
            return None

    v = BlankValues(facts.get("values") or {})
    return (
        f"{_month_day(v['report_date'])}，车间总产量日合计{_fmt_int(v['total_output_daily'])}吨"
        f"（外加工{_fmt_int(v['outsourced_daily'])}吨）比昨日{_delta_text(v['total_output_delta'], '吨')}，"
        f"月累计{_fmt_int(v['total_output_month'])}吨（外加工月累计{_fmt_int(v['outsourced_month'])}吨）。\n\n"
        f"铸轧分厂开机{_fmt_int(v['cast_roll_active_lines'])}条，日产量{_fmt_int(v['cast_roll_daily'])}吨，"
        f"月累计产量{_fmt_int(v['cast_roll_month'])}吨；铸锭车间日产量{_fmt_int(v['foundry_daily'])}吨，"
        f"月累计产量{_fmt_int(v['foundry_month'])}吨；热轧车间日产量{_fmt_int(v['hot_roll_daily'])}吨，"
        f"月累计产量{_fmt_int(v['hot_roll_month'])}吨；1650车间日产量{_fmt_int(v['cold_1650_daily'])}吨，"
        f"月累计产量{_fmt_int(v['cold_1650_month'])}吨，日道次{_fmt_int(v['cold_1650_pass_daily'])}道，"
        f"月累计道次{_fmt_int(v['cold_1650_pass_month'])}道；1850车间日产量{_fmt_int(v['cold_1850_daily'])}吨，"
        f"月累计产量{_fmt_int(v['cold_1850_month'])}吨，日道次{_fmt_int(v['cold_1850_pass_daily'])}道，"
        f"月累计道次{_fmt_int(v['cold_1850_pass_month'])}道；2050车间日产量{_fmt_int(v['cold_2050_daily'])}吨，"
        f"月累计产量{_fmt_int(v['cold_2050_month'])}吨，日道次{_fmt_int(v['cold_2050_pass_daily'])}道，"
        f"月累计道次{_fmt_int(v['cold_2050_pass_month'])}道；轧机日产量{_fmt_int(v['rolling_daily'])}吨，"
        f"月累计产量{_fmt_int(v['rolling_month'])}吨，日道次{_fmt_int(v['rolling_pass_daily'])}道，"
        f"月累计道次{_fmt_int(v['rolling_pass_month'])}道；在线退火日产量{_fmt_int(v['online_anneal_daily'])}吨，"
        f"月累计产量{_fmt_int(v['online_anneal_month'])}吨，拉矫日产量{_fmt_int(v['straightening_daily'])}吨，"
        f"月累计产量{_fmt_int(v['straightening_month'])}吨，精整车间日产量{_fmt_int(v['finishing_daily'])}吨，"
        f"月累计产量{_fmt_int(v['finishing_month'])}吨，剪切车间日产量{_fmt_int(v['shearing_daily'])}吨，"
        f"月累计产量{_fmt_int(v['shearing_month'])}吨，彩涂车间日产量{_fmt_int(v['coating_daily'])}吨，"
        f"月累计产量{_fmt_int(v['coating_month'])}吨；回收车间日产量{_fmt_int(v['recovery_daily'])}块，"
        f"月累计产量{_fmt_int(v['recovery_month'])}块，大修日磨辊{_fmt_int(v['roller_grind_daily'])}根，"
        f"月累计磨辊{_fmt_int(v['roller_grind_month'])}根。\n\n"
        f"当天在制料{_fmt_0_or_1(v['wip_total'])}吨，1650/2050冷轧{_fmt_0_or_1(v['wip_1650_2050_cold'])}吨，"
        f"1850冷轧{_fmt_0_or_1(v['wip_1850_cold'])}吨，铣床{_fmt_0_or_1(v['wip_milling'])}吨，"
        f"退火分厂{_fmt_0_or_1(v['wip_anneal_total'])}吨（新厂北线{_fmt_0_or_1(v['wip_new_north'])}吨，"
        f"新厂南线{_fmt_0_or_1(v['wip_new_south'])}吨，园区退火{_fmt_0_or_1(v['wip_park_anneal'])}吨），"
        f"精整分厂{_fmt_0_or_1(v['wip_finishing_total'])}吨（拉矫{_fmt_0_or_1(v['wip_straightening'])}吨、"
        f"精整{_fmt_0_or_1(v['wip_finishing'])}吨、园区精整{_fmt_0_or_1(v['wip_park_finishing'])}吨；"
        f"另热轧中厚板剪切{_fmt_0_or_1(v['wip_hot_plate_shearing'])}吨、彩涂{_fmt_0_or_1(v['wip_coating'])}吨）。"
        f"全厂高压总用电量{_fmt_int(v['total_electricity_kwh'])}度（分项用电{_fmt_int(v['subitem_electricity_kwh'])}度）；"
        f"铸轧用气{_fmt_int(v['cast_roll_gas_m3'])}m³（铸二{_fmt_int(v['cast_2_gas_m3'])}m³、"
        f"铸三{_fmt_int(v['cast_3_gas_m3'])}m³）、铸锭熔炼炉用气{_fmt_int(v['smelting_gas_m3'])}m³、"
        f"回收用气{_fmt_int(v['recovery_gas_m3'])}m³、热轧加热炉用气{_fmt_int(v['hot_roll_furnace_gas_m3'])}m³"
        f"（东炉{_fmt_int(v['east_furnace_gas_m3'])}m³、西炉{_fmt_int(v['west_furnace_gas_m3'])}m³）、"
        f"热轧锅炉用气{_fmt_int(v['hot_roll_boiler_gas_m3'])}m³、退火用气{_fmt_int(v['anneal_gas_m3'])}m³、"
        f"拉矫锅炉用气{_fmt_int(v['straightening_boiler_gas_m3'])}m³、新厂北线{_fmt_int(v['new_north_gas_m3'])}m³、"
        f"新厂南线{_fmt_int(v['new_south_gas_m3'])}m³、彩涂用气{_fmt_int(v['coating_gas_m3'])}m³、"
        f"餐厅用气{_fmt_int(v['canteen_gas_m3'])}m³，共计{_fmt_int(v['total_gas_m3'])}m³；"
        f"铸轧分厂日吨电耗{_fmt_1(v['cast_roll_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['cast_roll_electricity_per_ton_month'])}度，"
        f"日吨气耗{_fmt_1(v['cast_roll_gas_per_ton_daily'])}m³，月吨气耗{_fmt_1(v['cast_roll_gas_per_ton_month'])}m³；"
        f"铸锭车间日吨电耗{_fmt_1(v['foundry_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['foundry_electricity_per_ton_month'])}度，"
        f"日吨气耗{_fmt_1(v['foundry_gas_per_ton_daily'])}m³，月吨气耗{_fmt_1(v['foundry_gas_per_ton_month'])}m³；"
        f"热轧车间日吨电耗{_fmt_1(v['hot_roll_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['hot_roll_electricity_per_ton_month'])}度，"
        f"日吨气耗{_fmt_1(v['hot_roll_gas_per_ton_daily'])}m³，月吨气耗{_fmt_1(v['hot_roll_gas_per_ton_month'])}m³；"
        f"1650车间日吨电耗{_fmt_1(v['cold_1650_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['cold_1650_electricity_per_ton_month'])}度；"
        f"1850车间日吨电耗{_fmt_1(v['cold_1850_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['cold_1850_electricity_per_ton_month'])}度；"
        f"2050车间日吨电耗{_fmt_1(v['cold_2050_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['cold_2050_electricity_per_ton_month'])}度；"
        f"在线退火日吨电耗{_fmt_1(v['online_anneal_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['online_anneal_electricity_per_ton_month'])}度；"
        f"拉矫日吨电耗{_fmt_1(v['straightening_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['straightening_electricity_per_ton_month'])}度；"
        f"精整日吨电耗{_fmt_1(v['finishing_electricity_per_ton_daily'])}度，月吨电耗{_fmt_1(v['finishing_electricity_per_ton_month'])}度；"
        f"剪切日电耗{_fmt_1(v['shearing_electricity_per_ton_daily'])}度，月电耗{_fmt_1(v['shearing_electricity_per_ton_month'])}度；"
        f"彩涂日电耗{_fmt_1(v['coating_electricity_per_ton_daily'])}度，月电耗{_fmt_1(v['coating_electricity_per_ton_month'])}度，"
        f"日吨气耗{_fmt_1(v['coating_gas_per_ton_daily'])}m³，月吨气耗{_fmt_1(v['coating_gas_per_ton_month'])}m³。\n\n"
        f"入库成品日合计{_fmt_int(v['finished_inbound_daily'])}吨（寄存{_fmt_int(v['consignment_weight'])}吨），"
        f"月累计{_fmt_int(v['finished_inbound_month'])}吨。当天接合同{_fmt_int(v['daily_contract_weight'])}吨"
        f"（含热轧{_fmt_int(v['daily_hot_roll_contract_weight'])}吨）；冷轧日投料{_fmt_int(v['cold_roll_input_daily'])}吨"
        f"（2050投{_fmt_int(v['cold_2050_input_daily'])}吨、1850投{_fmt_int(v['cold_1850_input_daily'])}吨、"
        f"外加工{_fmt_int(v['outsourced_input_daily'])}吨），中厚板{_fmt_int(v['medium_plate_input_daily'])}吨，"
        f"总余合同量{_fmt_int(v['remaining_contract_weight'])}吨，比昨日{_delta_text(v['remaining_contract_delta'], '吨')}。\n\n"
        f"日成品率{_fmt_2(v['daily_yield_rate'])}%，比昨日{_delta_text(v['daily_yield_delta'], '%')}；"
        f"热轧成品率{_fmt_2(v['hot_roll_yield_rate'])}%，比昨日{_delta_text(v['hot_roll_yield_delta'], '%')}；"
        f"月成品率{_fmt_2(v['monthly_yield_rate'])}%（铸轧成品率{_fmt_2(v['cast_roll_yield_rate'])}%，"
        f"普板、卷成品率{_fmt_2(v['plate_coil_yield_rate'])}%，热轧成品率{_fmt_2(v['hot_roll_monthly_yield_rate'])}%）。\n\n"
        f"成本核算方面，电费约{_fmt_2(v['electricity_cost_10k'])}万元、气费约{_fmt_2(v['gas_cost_10k'])}万元，"
        f"已核合计约{_fmt_2(v['total_cost_10k'])}万元，按{_fmt_3(v['cost_basis_weight'])}吨折算约{_fmt_int(v['cost_per_ton'])}元/吨。"
    )


def build_template_daily_report_payload(
    db: Session,
    *,
    target_date: date,
    wip_date: date | None = None,
) -> dict[str, Any]:
    facts = build_template_daily_report_facts(db, target_date=target_date, wip_date=wip_date)
    validation = validate_template_daily_report_facts(facts)
    return {
        **validation,
        "target_date": target_date.isoformat(),
        "wip_date": facts.get("wip_date"),
        "facts": facts,
        "sources": facts.get("sources") or {},
    }


def apply_template_daily_report_to_report(
    db: Session,
    *,
    report: DailyReport,
    target_date: date,
    wip_date: date | None = None,
) -> dict[str, Any]:
    payload = build_template_daily_report_payload(db, target_date=target_date, wip_date=wip_date)
    report_data = dict(report.report_data or {})
    report_data[TEMPLATE_REPORT_KEY] = {
        "status": payload["status"],
        "text": payload.get("text"),
        "wip_date": payload.get("wip_date"),
        "missing_fields": payload.get("missing_fields") or [],
        "conflicts": payload.get("conflicts") or [],
        "sources": payload.get("sources") or {},
    }
    report.report_data = report_data
    if payload["status"] == "ready" and payload.get("text"):
        report.final_text_summary = str(payload["text"])
    return payload


def apply_template_daily_report_to_latest_report(
    db: Session,
    target_date: date,
    wip_date: date | None = None,
) -> dict[str, Any]:
    report = (
        db.query(DailyReport)
        .filter(DailyReport.report_date == target_date, DailyReport.report_type == "production")
        .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )
    if report is None:
        return {
            "status": "skipped",
            "text": None,
            "missing_fields": ["daily_report"],
            "conflicts": [],
            "target_date": target_date.isoformat(),
        }
    return apply_template_daily_report_to_report(db, report=report, target_date=target_date, wip_date=wip_date)
