from __future__ import annotations

from types import SimpleNamespace

from app.services.hermes_20_question_acceptance import _GENERIC_MISSING_ANSWER
from app.services.hermes_root_owner_production_orchestrator import _missing_next_step


def _next_step(metric_keys: tuple[str, ...], gap_items: list[dict] | None = None) -> str:
    return _missing_next_step(
        plan=SimpleNamespace(metric_keys=metric_keys),
        decision=SimpleNamespace(trace={'gap_plan': {'items': gap_items or []}}),
    )


def test_missing_anomaly_explanation_says_where_to_look_and_what_to_do() -> None:
    answer = _next_step(('anomaly_explanation_daily',))

    assert _GENERIC_MISSING_ANSWER not in answer
    assert '还没有写异常说明' in answer
    assert '异常页' in answer
    # 没有任何代码把钉钉内容写进这个字段，不能让人以为发到群里就能答
    assert '钉钉' not in answer


def test_a_field_specific_next_step_from_the_gap_plan_comes_first() -> None:
    answer = _next_step(
        ('total_electricity_kwh', 'anomaly_explanation_daily'),
        [{'field': 'total_electricity_kwh', 'next_step': '高压总用电优先采用钉钉能耗表'}],
    )

    assert answer == '高压总用电优先采用钉钉能耗表'


def test_other_fields_keep_the_generic_next_step() -> None:
    assert _GENERIC_MISSING_ANSWER in _next_step(('some_other_field',))
