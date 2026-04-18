from __future__ import annotations

from app.services.yield_rate_deprecation_map_service import build_yield_rate_deprecation_map


def test_build_yield_rate_deprecation_map_reports_formal_truth_and_items() -> None:
    payload = build_yield_rate_deprecation_map()

    assert payload['formal_truth'] == 'yield_matrix_lane'
    assert payload['statuses']['replace'] >= 1
    assert payload['statuses']['compat_only'] >= 1
    assert payload['statuses']['remove'] >= 1
    assert any(item['surface_id'] == 'live_dashboard.local_yield_recalc' for item in payload['items'])
    assert any(item['surface_id'] == 'report_push.summary_yield_rate' for item in payload['items'])
