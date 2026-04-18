from app.services.management_estimate_service import build_management_estimate


class _Runtime:
    MANAGEMENT_ESTIMATE_REVENUE_PER_TON = 1200.0
    MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT = 0.8
    MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT = 1.2
    MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE = 50.0


def test_build_management_estimate_computes_revenue_cost_and_margin():
    payload = build_management_estimate(
        contract_progress={
            'active_contract_count': 2,
            'stalled_contract_count': 1,
            'active_coil_count': 6,
            'stalled_coil_count': 2,
            'today_advanced_weight': 100.0,
            'remaining_weight': 300.0,
        },
        contract_lane={'daily_contract_weight': 150.0},
        energy_summary={'electricity_value': 100.0, 'gas_value': 40.0},
        mobile_summary={'reported_count': 8, 'unreported_count': 2, 'reporting_rate': 80.0},
        total_attendance=20,
        sync_status={'lag_seconds': 120, 'last_run_status': 'success'},
        runtime_settings=_Runtime(),
    )

    assert payload['estimate_ready'] is True
    assert payload['estimated_revenue'] == 180000.0
    assert payload['energy_cost'] == 128.0
    assert payload['labor_cost'] == 1000.0
    assert payload['estimated_cost'] == 1128.0
    assert payload['estimated_margin'] == 178872.0
