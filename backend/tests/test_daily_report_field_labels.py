from __future__ import annotations

from app.domain.daily_report_field_names import DAILY_REPORT_FIELD_LABELS, TEMPLATE_FIELD_GROUPS
from app.services.report.daily_fact_gap_closure_service import _field_label


def test_every_report_field_has_a_chinese_label() -> None:
    fields = {field for group in TEMPLATE_FIELD_GROUPS.values() for field in group}

    assert fields - set(DAILY_REPORT_FIELD_LABELS) == set()
    assert set(DAILY_REPORT_FIELD_LABELS) - fields == set()
    for field, label in DAILY_REPORT_FIELD_LABELS.items():
        assert label != field
        assert any('\u4e00' <= char <= '\u9fff' for char in label), field


def test_gap_titles_name_the_exact_field_instead_of_its_group() -> None:
    assert _field_label('outsourced_daily') == '外加工日产量'
    assert _field_label('cast_roll_daily') == '铸轧分厂日产量'
    assert _field_label('total_electricity_kwh') == '全厂高压总用电量'
