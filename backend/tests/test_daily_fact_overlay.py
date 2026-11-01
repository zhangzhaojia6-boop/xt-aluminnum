from __future__ import annotations

from app.services.report import daily_fact_overlay


def _fact(value, source_type='dingtalk_supplement'):
    return {'value': value, 'source_type': source_type}


BUNDLE_FACTS = {
    'daily_yield_rate': _fact(82.73),
    'monthly_yield_rate': _fact(84.38),
    'daily_contract_weight': _fact(563),
    'remaining_contract_weight': _fact(5160),
    'remaining_contract_delta': _fact(368.0),
}


def _overview():
    return {
        'plant_output': {'daily_output': 511.35, 'yield_rate': None, 'monthly_yield_rate': None, 'yield_rate_source': 'unavailable_requires_same_basis'},
        'yield_rates': {'daily': None, 'monthly': None},
        'contracts': {'daily_new': None, 'remaining': None, 'remaining_delta': None, 'quality_status': 'missing'},
        'header_kpis': [
            {'key': 'plant_daily_output', 'value': 511.35},
            {'key': 'daily_yield', 'value': None, 'delta': None},
            {'key': 'daily_contracts', 'value': None},
            {'key': 'remaining_contracts', 'value': None, 'delta': None, 'delta_label': None},
        ],
    }


def test_daily_overview_shows_persisted_daily_facts_with_their_source() -> None:
    overview = daily_fact_overlay.overlay_daily_overview(_overview(), BUNDLE_FACTS)

    assert overview['yield_rates']['daily'] == 82.73
    assert overview['yield_rates']['monthly'] == 84.38
    assert overview['yield_rates']['source'] == 'dingtalk_supplement'
    assert overview['plant_output']['yield_rate'] == 82.73
    assert overview['plant_output']['monthly_yield_rate'] == 84.38
    assert overview['plant_output']['yield_rate_source'] == 'dingtalk_supplement'
    assert overview['contracts']['daily_new'] == 563
    assert overview['contracts']['remaining'] == 5160
    assert overview['contracts']['remaining_delta'] == 368.0
    kpis = {kpi['key']: kpi for kpi in overview['header_kpis']}
    assert kpis['plant_daily_output']['value'] == 511.35
    assert kpis['daily_yield']['value'] == 82.73
    assert kpis['daily_contracts']['value'] == 563
    assert kpis['remaining_contracts']['value'] == 5160
    assert kpis['remaining_contracts']['delta'] == 368.0
    assert kpis['remaining_contracts']['delta_label'] == '比昨日 ↑368.0'
    assert overview['fact_overlay']['daily_yield_rate'] == 'dingtalk_supplement'


def test_daily_overview_is_unchanged_without_persisted_facts() -> None:
    overview = daily_fact_overlay.overlay_daily_overview(_overview(), {})

    assert overview == _overview()


def _factory_dashboard(*, yield_rate):
    return {
        'leader_metrics': {'yield_rate': None, 'contract_weight': 0.0, 'today_total_output': 511.35},
        'leader_summary': {
            'summary_source': 'deterministic',
            'summary_text': '本次不生成最终日报正文。',
            'metrics': {
                'report_date': '2026-10-31',
                'total_output_weight': 511.35,
                'energy_available': False,
                'yield_rate': yield_rate,
                'contract_weight': 0.0,
            },
        },
    }


def test_factory_dashboard_uses_persisted_yield_and_contract() -> None:
    dashboard = daily_fact_overlay.overlay_factory_dashboard(_factory_dashboard(yield_rate=0.0), BUNDLE_FACTS)

    for metrics in (dashboard['leader_metrics'], dashboard['leader_summary']['metrics']):
        assert metrics['yield_rate'] == 82.73
        assert metrics['contract_weight'] == 563
    assert '成品率' not in dashboard['leader_summary']['summary_text']
    assert '能耗数据缺失' in dashboard['leader_summary']['summary_text']


def test_factory_dashboard_reports_zero_yield_as_missing_without_persisted_yield() -> None:
    dashboard = daily_fact_overlay.overlay_factory_dashboard(_factory_dashboard(yield_rate=0.0), {})

    assert dashboard['leader_summary']['metrics']['yield_rate'] is None
    assert dashboard['leader_metrics']['yield_rate'] is None
    assert dashboard['leader_summary']['metrics']['contract_weight'] == 0.0
    assert '全厂成品率缺失' in dashboard['leader_summary']['summary_text']


def test_latest_daily_fact_values_needs_a_database_session() -> None:
    assert daily_fact_overlay.latest_daily_fact_values(object(), target_date=None) == {}
