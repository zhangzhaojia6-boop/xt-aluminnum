from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ManagementEstimateAssumptions:
    revenue_per_ton: float | None = None
    electricity_cost_per_unit: float | None = None
    gas_cost_per_unit: float | None = None
    labor_cost_per_attendance: float | None = None


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_assumptions(runtime_settings=None) -> ManagementEstimateAssumptions:
    runtime = runtime_settings
    return ManagementEstimateAssumptions(
        revenue_per_ton=getattr(runtime, 'MANAGEMENT_ESTIMATE_REVENUE_PER_TON', None) if runtime else None,
        electricity_cost_per_unit=getattr(runtime, 'MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT', None) if runtime else None,
        gas_cost_per_unit=getattr(runtime, 'MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT', None) if runtime else None,
        labor_cost_per_attendance=getattr(runtime, 'MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE', None) if runtime else None,
    )


def build_management_estimate(
    *,
    contract_progress: dict[str, Any],
    contract_lane: dict[str, Any],
    energy_summary: dict[str, Any],
    mobile_summary: dict[str, Any],
    total_attendance: int,
    sync_status: dict[str, Any] | None = None,
    runtime_settings=None,
) -> dict[str, Any]:
    assumptions = _resolve_assumptions(runtime_settings)

    estimated_revenue = None
    if assumptions.revenue_per_ton is not None:
        estimated_revenue = round(
            _to_float(contract_lane.get('daily_contract_weight')) * assumptions.revenue_per_ton,
            2,
        )

    energy_cost = None
    if assumptions.electricity_cost_per_unit is not None or assumptions.gas_cost_per_unit is not None:
        electricity_cost = _to_float(energy_summary.get('electricity_value')) * _to_float(assumptions.electricity_cost_per_unit)
        gas_cost = _to_float(energy_summary.get('gas_value')) * _to_float(assumptions.gas_cost_per_unit)
        energy_cost = round(electricity_cost + gas_cost, 2)

    labor_cost = None
    if assumptions.labor_cost_per_attendance is not None:
        labor_cost = round(total_attendance * assumptions.labor_cost_per_attendance, 2)

    estimated_cost = None
    if energy_cost is not None or labor_cost is not None:
        estimated_cost = round(_to_float(energy_cost) + _to_float(labor_cost), 2)

    estimated_margin = None
    if estimated_revenue is not None and estimated_cost is not None:
        estimated_margin = round(estimated_revenue - estimated_cost, 2)

    return {
        'estimate_ready': estimated_revenue is not None and estimated_cost is not None,
        'estimated_revenue': estimated_revenue,
        'estimated_cost': estimated_cost,
        'estimated_margin': estimated_margin,
        'energy_cost': energy_cost,
        'labor_cost': labor_cost,
        'active_contract_count': int(contract_progress.get('active_contract_count') or 0),
        'stalled_contract_count': int(contract_progress.get('stalled_contract_count') or 0),
        'active_coil_count': int(contract_progress.get('active_coil_count') or 0),
        'stalled_coil_count': int(contract_progress.get('stalled_coil_count') or 0),
        'today_advanced_weight': round(_to_float(contract_progress.get('today_advanced_weight')), 2),
        'remaining_weight': round(_to_float(contract_progress.get('remaining_weight')), 2),
        'reported_shift_count': int(mobile_summary.get('reported_count') or 0),
        'unreported_shift_count': int(mobile_summary.get('unreported_count') or 0),
        'reporting_rate': round(_to_float(mobile_summary.get('reporting_rate')), 2),
        'total_attendance': int(total_attendance or 0),
        'sync_lag_seconds': sync_status.get('lag_seconds') if sync_status else None,
        'sync_status': sync_status.get('last_run_status') if sync_status else 'idle',
        'assumptions': {
            'revenue_per_ton': assumptions.revenue_per_ton,
            'electricity_cost_per_unit': assumptions.electricity_cost_per_unit,
            'gas_cost_per_unit': assumptions.gas_cost_per_unit,
            'labor_cost_per_attendance': assumptions.labor_cost_per_attendance,
        },
    }
