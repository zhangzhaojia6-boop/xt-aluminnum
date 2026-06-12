from types import SimpleNamespace

from app.core.active_workshops import (
    ACTIVE_PRODUCTION_WORKSHOP_NAMES,
    filter_active_production_workshops,
    get_workshop_data_source_policy,
    is_active_production_workshop_name,
    normalize_workshop_name,
)


def test_active_workshop_names_include_quenching_as_thirteen_workshops():
    assert len(ACTIVE_PRODUCTION_WORKSHOP_NAMES) == 13
    assert '淬火车间' in ACTIVE_PRODUCTION_WORKSHOP_NAMES


def test_workshop_aliases_normalize_mes_and_master_names():
    assert normalize_workshop_name('铸轧二') == '铸二'
    assert normalize_workshop_name('铸轧三') == '铸三'
    assert normalize_workshop_name('1650冷轧') == '冷轧1650'
    assert normalize_workshop_name('2050冷轧车间') == '冷轧2050'
    assert normalize_workshop_name('园区淬火') == '淬火车间'
    assert is_active_production_workshop_name('淬火') is True


def test_active_workshop_filter_keeps_only_active_code_or_active_name():
    rows = [
        SimpleNamespace(code='CH', name='园区淬火'),
        SimpleNamespace(code='', name='铸轧二'),
        SimpleNamespace(code='', name='历史车间'),
        SimpleNamespace(code='OLD', name='旧别名'),
    ]

    filtered = filter_active_production_workshops(rows)

    assert [item.name for item in filtered] == ['园区淬火', '铸轧二']


def test_no_terminal_workshop_policy_separates_billet_and_mes_primary_workshops():
    assert get_workshop_data_source_policy('热轧')['primary_source'] == 'manual_billet_input'
    assert get_workshop_data_source_policy('铸三')['primary_source'] == 'manual_billet_input'
    assert get_workshop_data_source_policy('铸锭')['primary_source'] == 'manual_daily_summary'
    assert get_workshop_data_source_policy('淬火车间')['has_terminal'] is False
    assert get_workshop_data_source_policy('精整')['primary_source'] == 'mes'
