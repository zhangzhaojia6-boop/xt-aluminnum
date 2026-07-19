from __future__ import annotations

import re
from datetime import date
from typing import Any


_NUMBER = r"(-?\d+(?:\.\d+)?)"
_SIGNED = r"([↑↓])(\d+(?:\.\d+)?)"


def _float(value: str) -> float:
    return float(value)


def _number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return None
    return _float(match.group(1))


def _signed_delta(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return None
    sign = 1 if match.group(1) == "↑" else -1
    return sign * _float(match.group(2))


def _set_if_found(values: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        values[key] = value


def parse_output_skill_daily_report(text: str) -> dict[str, Any]:
    """Parse the locked Chinese daily-report body into the template fact keys."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    values: dict[str, Any] = {}

    date_match = re.search(r"(\d{1,2})月(\d{1,2})日", normalized)
    if date_match:
        values["report_date"] = date(2026, int(date_match.group(1)), int(date_match.group(2)))

    _set_if_found(values, "total_output_daily", _number(normalized, rf"车间总产量日合计{_NUMBER}吨"))
    _set_if_found(values, "outsourced_daily", _number(normalized, rf"外加工{_NUMBER}吨"))
    _set_if_found(values, "total_output_delta", _signed_delta(normalized, rf"比昨日{_SIGNED}吨"))
    _set_if_found(values, "total_output_month", _number(normalized, rf"月累计{_NUMBER}吨（外加工月累计"))
    _set_if_found(values, "outsourced_month", _number(normalized, rf"外加工月累计{_NUMBER}吨"))

    workshop_patterns = {
        "cast_roll_active_lines": rf"铸轧分厂开机{_NUMBER}条",
        "cast_roll_daily": rf"铸轧分厂(?:开机\d+(?:\.\d+)?条[，,])?日产量{_NUMBER}吨",
        "cast_roll_month": rf"铸轧分厂.*?月累计产量{_NUMBER}吨；铸锭车间",
        "foundry_daily": rf"铸锭车间日产量{_NUMBER}吨",
        "foundry_month": rf"铸锭车间日产量.*?月累计产量{_NUMBER}吨；热轧车间",
        "hot_roll_daily": rf"热轧车间日产量{_NUMBER}吨",
        "hot_roll_month": rf"热轧车间日产量.*?月累计产量{_NUMBER}吨；1650车间",
        "cold_1650_daily": rf"1650车间日产量{_NUMBER}吨",
        "cold_1650_month": rf"1650车间日产量.*?月累计产量{_NUMBER}吨，日道次",
        "cold_1650_pass_daily": rf"1650车间日产量.*?日道次{_NUMBER}道",
        "cold_1650_pass_month": rf"1650车间日产量.*?月累计道次{_NUMBER}道；1850车间",
        "cold_1850_daily": rf"1850车间日产量{_NUMBER}吨",
        "cold_1850_month": rf"1850车间日产量.*?月累计产量{_NUMBER}吨，日道次",
        "cold_1850_pass_daily": rf"1850车间日产量.*?日道次{_NUMBER}道",
        "cold_1850_pass_month": rf"1850车间日产量.*?月累计道次{_NUMBER}道；2050车间",
        "cold_2050_daily": rf"2050车间日产量{_NUMBER}吨",
        "cold_2050_month": rf"2050车间日产量.*?月累计产量{_NUMBER}吨，日道次",
        "cold_2050_pass_daily": rf"2050车间日产量.*?日道次{_NUMBER}道",
        "cold_2050_pass_month": rf"2050车间日产量.*?月累计道次{_NUMBER}道；轧机",
        "rolling_daily": rf"轧机日产量{_NUMBER}吨",
        "rolling_month": rf"轧机日产量.*?月累计产量{_NUMBER}吨，日道次",
        "rolling_pass_daily": rf"轧机日产量.*?日道次{_NUMBER}道",
        "rolling_pass_month": rf"轧机日产量.*?月累计道次{_NUMBER}道；在线退火",
        "online_anneal_daily": rf"在线退火日产量{_NUMBER}吨",
        "online_anneal_month": rf"在线退火日产量.*?月累计产量{_NUMBER}吨，拉矫",
        "straightening_daily": rf"拉矫日产量{_NUMBER}吨",
        "straightening_month": rf"拉矫日产量.*?月累计产量{_NUMBER}吨，精整车间",
        "finishing_daily": rf"精整车间日产量{_NUMBER}吨",
        "finishing_month": rf"精整车间日产量.*?月累计产量{_NUMBER}吨，剪切车间",
        "shearing_daily": rf"剪切车间日产量{_NUMBER}吨",
        "shearing_month": rf"剪切车间日产量.*?月累计产量{_NUMBER}吨，彩涂车间",
        "coating_daily": rf"彩涂车间日产量{_NUMBER}吨",
        "coating_month": rf"彩涂车间日产量.*?月累计产量{_NUMBER}吨；回收车间",
        "recovery_daily": rf"回收车间日产量{_NUMBER}块",
        "recovery_month": rf"回收车间日产量.*?月累计产量{_NUMBER}块",
        "roller_grind_daily": rf"大修日磨辊{_NUMBER}根",
        "roller_grind_month": rf"月累计磨辊{_NUMBER}根",
    }
    for key, pattern in workshop_patterns.items():
        _set_if_found(values, key, _number(normalized, pattern))

    wip_patterns = {
        "wip_total": rf"当天在制料{_NUMBER}吨",
        "wip_1650_2050_cold": rf"1650/2050冷轧{_NUMBER}吨",
        "wip_1850_cold": rf"1850冷轧{_NUMBER}吨",
        "wip_milling": rf"铣床{_NUMBER}吨",
        "wip_anneal_total": rf"退火分厂{_NUMBER}吨",
        "wip_new_north": rf"新厂北线{_NUMBER}吨",
        "wip_new_south": rf"新厂南线{_NUMBER}吨",
        "wip_park_anneal": rf"园区退火{_NUMBER}吨",
        "wip_finishing_total": rf"精整分厂{_NUMBER}吨",
        "wip_straightening": rf"拉矫{_NUMBER}吨、精整",
        "wip_finishing": rf"拉矫\d+(?:\.\d+)?吨、精整{_NUMBER}吨、园区精整",
        "wip_park_finishing": rf"园区精整{_NUMBER}吨",
        "wip_hot_plate_shearing": rf"热轧中厚板剪切{_NUMBER}吨",
        "wip_coating": rf"热轧中厚板剪切\d+(?:\.\d+)?吨、彩涂{_NUMBER}吨",
    }
    for key, pattern in wip_patterns.items():
        _set_if_found(values, key, _number(normalized, pattern))

    energy_patterns = {
        "total_electricity_kwh": rf"全厂高压总用电量{_NUMBER}度",
        "subitem_electricity_kwh": rf"分项用电{_NUMBER}度",
        "cast_roll_gas_m3": rf"铸轧用气{_NUMBER}m³",
        "cast_2_gas_m3": rf"铸二{_NUMBER}m³",
        "cast_3_gas_m3": rf"铸三{_NUMBER}m³",
        "smelting_gas_m3": rf"铸锭熔炼炉用气{_NUMBER}m³",
        "recovery_gas_m3": rf"回收用气{_NUMBER}m³",
        "hot_roll_furnace_gas_m3": rf"热轧加热炉用气{_NUMBER}m³",
        "east_furnace_gas_m3": rf"东炉{_NUMBER}m³",
        "west_furnace_gas_m3": rf"西炉{_NUMBER}m³",
        "hot_roll_boiler_gas_m3": rf"热轧锅炉用气{_NUMBER}m³",
        "anneal_gas_m3": rf"退火用气{_NUMBER}m³",
        "straightening_boiler_gas_m3": rf"拉矫锅炉用气{_NUMBER}m³",
        "new_north_gas_m3": rf"新厂北线{_NUMBER}m³",
        "new_south_gas_m3": rf"新厂南线{_NUMBER}m³",
        "coating_gas_m3": rf"彩涂用气{_NUMBER}m³",
        "canteen_gas_m3": rf"餐厅用气{_NUMBER}m³",
        "total_gas_m3": rf"共计{_NUMBER}m³",
        "cast_roll_electricity_per_ton_daily": rf"铸轧分厂日吨电耗{_NUMBER}度",
        "cast_roll_electricity_per_ton_month": rf"铸轧分厂日吨电耗[^；。]*?月吨电耗{_NUMBER}度",
        "cast_roll_gas_per_ton_daily": rf"铸轧分厂日吨电耗[^；。]*?日吨气耗{_NUMBER}m³",
        "cast_roll_gas_per_ton_month": rf"铸轧分厂日吨电耗[^；。]*?月吨气耗{_NUMBER}m³",
        "foundry_electricity_per_ton_daily": rf"铸锭车间日吨电耗{_NUMBER}度",
        "foundry_electricity_per_ton_month": rf"铸锭车间日吨电耗[^；。]*?月吨电耗{_NUMBER}度",
        "foundry_gas_per_ton_daily": rf"铸锭车间日吨电耗[^；。]*?日吨气耗{_NUMBER}m³",
        "foundry_gas_per_ton_month": rf"铸锭车间日吨电耗[^；。]*?月吨气耗{_NUMBER}m³",
        "hot_roll_electricity_per_ton_daily": rf"热轧车间日吨电耗{_NUMBER}度",
        "hot_roll_electricity_per_ton_month": rf"热轧车间日吨电耗[^；。]*?月吨电耗{_NUMBER}度",
        "hot_roll_gas_per_ton_daily": rf"热轧车间日吨电耗[^；。]*?日吨气耗{_NUMBER}m³",
        "hot_roll_gas_per_ton_month": rf"热轧车间日吨电耗[^；。]*?月吨气耗{_NUMBER}m³",
        "cold_1650_electricity_per_ton_daily": rf"1650车间日吨电耗{_NUMBER}度",
        "cold_1650_electricity_per_ton_month": rf"1650车间日吨电耗.*?月吨电耗{_NUMBER}度",
        "cold_1850_electricity_per_ton_daily": rf"1850车间日吨电耗{_NUMBER}度",
        "cold_1850_electricity_per_ton_month": rf"1850车间日吨电耗.*?月吨电耗{_NUMBER}度",
        "cold_2050_electricity_per_ton_daily": rf"2050车间日吨电耗{_NUMBER}度",
        "cold_2050_electricity_per_ton_month": rf"2050车间日吨电耗.*?月吨电耗{_NUMBER}度",
        "online_anneal_electricity_per_ton_daily": rf"在线退火日吨电耗{_NUMBER}度",
        "online_anneal_electricity_per_ton_month": rf"在线退火日吨电耗.*?月吨电耗{_NUMBER}度",
        "straightening_electricity_per_ton_daily": rf"拉矫日吨电耗{_NUMBER}度",
        "straightening_electricity_per_ton_month": rf"拉矫日吨电耗.*?月吨电耗{_NUMBER}度",
        "finishing_electricity_per_ton_daily": rf"精整日吨电耗{_NUMBER}度",
        "finishing_electricity_per_ton_month": rf"精整日吨电耗.*?月吨电耗{_NUMBER}度",
        "shearing_electricity_per_ton_daily": rf"剪切日电耗{_NUMBER}度",
        "shearing_electricity_per_ton_month": rf"剪切日电耗.*?月电耗{_NUMBER}度",
        "coating_electricity_per_ton_daily": rf"彩涂日电耗{_NUMBER}度",
        "coating_electricity_per_ton_month": rf"彩涂日电耗.*?月电耗{_NUMBER}度",
        "coating_gas_per_ton_daily": rf"彩涂日电耗.*?日吨气耗{_NUMBER}m³",
        "coating_gas_per_ton_month": rf"彩涂日电耗.*?月吨气耗{_NUMBER}m³",
    }
    for key, pattern in energy_patterns.items():
        _set_if_found(values, key, _number(normalized, pattern))

    contract_patterns = {
        "finished_inbound_daily": rf"入库成品日合计{_NUMBER}吨",
        "consignment_weight": rf"寄存{_NUMBER}吨",
        "finished_inbound_month": rf"入库成品日合计.*?月累计{_NUMBER}吨",
        "daily_contract_weight": rf"当天接合同{_NUMBER}吨",
        "daily_hot_roll_contract_weight": rf"含热轧{_NUMBER}吨",
        "cold_roll_input_daily": rf"冷轧日投料{_NUMBER}吨",
        "cold_2050_input_daily": rf"2050投{_NUMBER}吨",
        "cold_1850_input_daily": rf"1850投{_NUMBER}吨",
        "outsourced_input_daily": rf"冷轧日投料[^。；\n]*?外加工{_NUMBER}吨[)）]",
        "medium_plate_input_daily": rf"中厚板{_NUMBER}吨",
        "remaining_contract_weight": rf"总余合同量{_NUMBER}吨",
    }
    for key, pattern in contract_patterns.items():
        _set_if_found(values, key, _number(normalized, pattern))
    _set_if_found(values, "remaining_contract_delta", _signed_delta(normalized, rf"总余合同量.*?比昨日{_SIGNED}吨"))

    yield_patterns = {
        "daily_yield_rate": rf"日成品率{_NUMBER}%",
        "hot_roll_yield_rate": rf"热轧成品率{_NUMBER}%",
        "monthly_yield_rate": rf"月成品率{_NUMBER}%",
        "cast_roll_yield_rate": rf"铸轧成品率{_NUMBER}%",
        "plate_coil_yield_rate": rf"普板、卷成品率{_NUMBER}%",
        "hot_roll_monthly_yield_rate": rf"月成品率.*?热轧成品率{_NUMBER}%[)）]",
    }
    for key, pattern in yield_patterns.items():
        _set_if_found(values, key, _number(normalized, pattern))
    _set_if_found(values, "daily_yield_delta", _signed_delta(normalized, rf"日成品率.*?比昨日{_SIGNED}%"))
    _set_if_found(values, "hot_roll_yield_delta", _signed_delta(normalized, rf"热轧成品率.*?比昨日{_SIGNED}%"))

    cost_patterns = {
        "electricity_cost_10k": rf"电费约{_NUMBER}万元",
        "gas_cost_10k": rf"气费约{_NUMBER}万元",
        "total_cost_10k": rf"已核合计约{_NUMBER}万元",
        "cost_basis_weight": rf"按{_NUMBER}吨折算",
        "cost_per_ton": rf"折算约{_NUMBER}元/吨",
    }
    for key, pattern in cost_patterns.items():
        _set_if_found(values, key, _number(normalized, pattern))

    return values
