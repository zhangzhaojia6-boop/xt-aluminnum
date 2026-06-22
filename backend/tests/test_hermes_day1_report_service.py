from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any


BUSINESS_DATE = date(2026, 6, 21)
BLOCKED_SENTENCE = '当前关键字段缺失，Hermes 未生成正式日报正文；请先补齐缺失字段后重跑。'


def _service():
    return import_module('app.services.hermes_day1_report_service')


def _workshop_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        'cast_roll_daily': 104,
        'cast_roll_month': 1662,
        'cast_roll_electricity_per_ton_daily': 96.7,
        'cast_roll_electricity_per_ton_month': 80.6,
        'cast_roll_gas_per_ton_daily': 148.1,
        'cast_roll_gas_per_ton_month': 121.3,
        'foundry_daily': 261,
        'foundry_month': 5576,
        'foundry_electricity_per_ton_daily': 24.3,
        'foundry_electricity_per_ton_month': 28.0,
        'foundry_gas_per_ton_daily': 71.0,
        'foundry_gas_per_ton_month': 81.6,
        'hot_roll_daily': 251,
        'hot_roll_month': 5230,
        'hot_roll_electricity_per_ton_daily': 158.4,
        'hot_roll_electricity_per_ton_month': 131.7,
        'hot_roll_gas_per_ton_daily': 29.8,
        'hot_roll_gas_per_ton_month': 26.7,
        'cold_1650_daily': 130,
        'cold_1650_month': 2819,
        'cold_1650_electricity_per_ton_daily': 111.8,
        'cold_1650_electricity_per_ton_month': 83.6,
        'cold_1850_daily': 46,
        'cold_1850_month': 816,
        'cold_1850_electricity_per_ton_daily': 117.8,
        'cold_1850_electricity_per_ton_month': 108.5,
        'cold_2050_daily': 80,
        'cold_2050_month': 2422,
        'cold_2050_electricity_per_ton_daily': 223.1,
        'cold_2050_electricity_per_ton_month': 157.4,
        'online_anneal_daily': 375,
        'online_anneal_month': 6274,
        'online_anneal_electricity_per_ton_daily': 66.9,
        'online_anneal_electricity_per_ton_month': 55.0,
        'straightening_daily': 64,
        'straightening_month': 2677,
        'straightening_electricity_per_ton_daily': 14.5,
        'straightening_electricity_per_ton_month': 16.5,
        'finishing_daily': 37,
        'finishing_month': 1592,
        'finishing_electricity_per_ton_daily': 11.5,
        'finishing_electricity_per_ton_month': 8.6,
        'shearing_daily': 144,
        'shearing_month': 1609,
        'shearing_electricity_per_ton_daily': 14.9,
        'shearing_electricity_per_ton_month': 15.6,
        'coating_daily': 0,
        'coating_month': 0,
        'coating_electricity_per_ton_daily': 0.0,
        'coating_electricity_per_ton_month': 0.0,
        'coating_gas_per_ton_daily': 0.0,
        'coating_gas_per_ton_month': 0.0,
        'recovery_daily': 67,
        'recovery_month': 1332,
    }
    values.update(overrides)
    return values


def _sources(
    *,
    template_status: str = 'ready',
    template_text: str | None = '  6月21日，车间总产量日合计366吨。  ',
    values: dict[str, Any] | None = None,
    missing_fields: list[str] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    audit_run: dict[str, Any] | None = None,
    output_skill_alignment: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fact_values = _workshop_values(**(values or {}))
    fact_sources = {key: {'source_type': '数据中枢 facts'} for key in fact_values}
    payload: dict[str, Any] = {
        'trace_id': 'trace-day1-001',
        'template_daily_report': {
            'status': template_status,
            'text': template_text,
            'missing_fields': missing_fields or [],
            'conflicts': conflicts or [],
            'facts': {'values': fact_values, 'sources': fact_sources},
        },
        'audit_run': audit_run
        or {
            'status': 'completed',
            'match_rate': 0.98,
            'source_status': {'mes': 'ok', 'hub': 'ok', 'output_skill': 'parsed'},
            'source_errors': {},
            'diffs': {},
            'suggested_actions': ['继续核对异常吨耗'],
        },
        'output_skill_alignment': output_skill_alignment if output_skill_alignment is not None else {'field_match_rate': 98.5},
        'dingtalk_evidence': [],
        'dingtalk_messages': [],
        'rag': {'answer': '模板说明', 'citations': []},
        'historical_reports': [],
    }
    if extra:
        payload.update(extra)
    return payload


def test_workshop_detail_specs_cover_day1_required_workshops() -> None:
    service = _service()

    assert service.WORKSHOP_DETAIL_SPECS == (
        ('铸轧分厂', 'cast_roll'),
        ('铸锭车间', 'foundry'),
        ('热轧车间', 'hot_roll'),
        ('1650车间', 'cold_1650'),
        ('1850车间', 'cold_1850'),
        ('2050车间', 'cold_2050'),
        ('在线退火', 'online_anneal'),
        ('拉矫', 'straightening'),
        ('精整车间', 'finishing'),
        ('剪切车间', 'shearing'),
        ('彩涂车间', 'coating'),
        ('回收车间', 'recovery'),
    )


def test_ready_template_produces_three_sections_and_preserves_formal_text() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(),
    )

    assert result['status'] == 'ready'
    assert result['formal_text'] == '6月21日，车间总产量日合计366吨。'
    assert result['text'].count('工厂大脑判断单') == 1
    assert result['text'].count('正式日报正文') == 1
    assert result['text'].count('各车间明细') == 1
    assert result['text'].index('工厂大脑判断单') < result['text'].index('正式日报正文')
    assert result['text'].index('正式日报正文') < result['text'].index('各车间明细')
    assert '6月21日，车间总产量日合计366吨。' in result['text']
    assert len(result['workshop_details']) == 12
    assert '【2050车间】' in result['text']
    assert '日产量：80吨，月累计：2422吨。' in result['text']
    assert '日吨电耗：223.1度，月吨电耗：157.4度。' in result['text']
    assert 'Hermes判断' in result['text']
    assert 'None' not in result['text']
    assert 'null' not in result['text']


def test_blocked_template_does_not_fake_formal_text_and_shows_missing_fields() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            template_status='blocked',
            template_text=None,
            missing_fields=['total_output_daily', 'wip_total'],
            audit_run={
                'status': 'failed',
                'match_rate': None,
                'source_status': {'mes': 'failed', 'hub': 'ok'},
                'source_errors': {'mes': '连接超时'},
                'diffs': {},
                'suggested_actions': ['先补齐模板字段'],
            },
            output_skill_alignment={},
        ),
    )

    assert result['status'] == 'blocked'
    assert result['formal_text'] == ''
    assert BLOCKED_SENTENCE in result['text']
    assert '车间总产量日合计366吨' not in result['text']
    assert 'total_output_daily' in result['text']
    assert 'wip_total' in result['text']
    assert '缺失字段' in result['text']
    assert 'MES 只读数据源读取不完整' in result['text']
    assert result['brain_judgment']['missing_fields'] == ['total_output_daily', 'wip_total']


def test_conflicts_and_source_errors_are_visible_in_judgment_and_text() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            conflicts=[
                {
                    'field': 'total_output_daily',
                    'message': '模板日报与输出 skill 不一致',
                    'sources': ['template_daily_report', 'output_skill'],
                }
            ],
            audit_run={
                'status': 'completed',
                'match_rate': 0.91,
                'source_status': {'mes': 'ok', 'hub': 'ok', 'output_skill': 'parsed'},
                'source_errors': {'output_skill': '字段 total_output_daily 缺少单位'},
                'diffs': {
                    'total_output_daily': {
                        'status': 'mismatch',
                        'hub_value': 366,
                        'output_skill_value': 360,
                    },
                    'cold_2050_daily': {'status': 'matched'},
                },
                'suggested_actions': ['复核输出 skill 的总产量'],
            },
            output_skill_alignment={},
        ),
    )

    conflict_text = str(result['brain_judgment'])
    assert 'total_output_daily' in conflict_text
    assert '模板日报与输出 skill 不一致' in conflict_text
    assert '字段 total_output_daily 缺少单位' in conflict_text
    assert 'mismatch' in conflict_text
    assert '发现冲突' in result['text']
    assert '复核输出 skill 的总产量' in result['text']


def test_suggested_action_dicts_render_as_readable_text_without_raw_repr() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            audit_run={
                'status': 'completed',
                'match_rate': 0.99,
                'source_status': {'mes': 'ok', 'hub': 'ok', 'output_skill': 'parsed'},
                'source_errors': {},
                'diffs': {},
                'suggested_actions': [
                    {
                        'action_type': 'mapping_alias_upsert',
                        'risk_level': 'low',
                        'target_key': 'cold-roll:2050',
                        'field_name': 'workshop_output',
                        'before_value': {'hub': 95.0},
                        'after_value': {'hub': 100.0},
                        'evidence': {'source': 'mes'},
                    }
                ],
            },
        ),
    )

    assert '动作=mapping_alias_upsert' in result['text']
    assert '风险=low' in result['text']
    assert '字段=workshop_output' in result['text']
    assert '目标=cold-roll:2050' in result['text']
    assert 'action_type' not in result['text']
    assert "{'action_type'" not in result['text']
    assert '{' not in result['text']
    assert '}' not in result['text']


def test_realistic_audit_diff_values_are_rendered_in_conflicts() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            audit_run={
                'status': 'completed',
                'match_rate': 0.66,
                'source_status': {'mes': 'ok', 'hub': 'ok', 'output_skill': 'parsed'},
                'source_errors': {},
                'diffs': {
                    'total_output': {
                        'status': 'hub_mismatch',
                        'values': {'hub': 95.0, 'mes': 100.0, 'output_skill': 98.0},
                    }
                },
                'suggested_actions': [],
            },
            output_skill_alignment={},
        ),
    )

    assert 'total_output' in result['text']
    assert 'hub_mismatch' in result['text']
    assert '数据中枢=95' in result['text']
    assert '外部 MES=100' in result['text']
    assert '输出 skill=98' in result['text']
    assert "{'hub'" not in result['text']


def test_empty_optional_sources_are_not_listed_as_checked_sources() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            output_skill_alignment={},
            extra={
                'dingtalk_evidence': [],
                'dingtalk_messages': [],
                'historical_reports': [],
                'rag': {'answer': None, 'citations': [], 'status': 'failed'},
            },
        ),
    )

    source_names = result['brain_judgment']['source_names']
    assert '模板正式日报' in source_names
    assert 'Hermes 数据审计' in source_names
    assert '钉钉证据' not in source_names
    assert '钉钉文本' not in source_names
    assert 'RAG 知识库' not in source_names
    assert '历史日报' not in source_names
    assert '输出 skill 对齐' not in source_names


def test_failed_historical_report_without_final_text_is_not_listed_as_checked_source() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            extra={
                'historical_reports': [
                    {
                        'report_date': '2026-06-20',
                        'status': 'failed',
                        'quality_gate_status': 'failed',
                        'has_final_text': False,
                        'delivery_ready': False,
                    }
                ]
            },
        ),
    )

    assert '历史日报' not in result['brain_judgment']['source_names']


def test_meaningful_historical_report_is_listed_as_checked_source() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            extra={
                'historical_reports': [
                    {
                        'report_date': '2026-06-20',
                        'status': 'published',
                        'quality_gate_status': 'passed',
                        'has_final_text': True,
                        'delivery_ready': True,
                    }
                ]
            },
        ),
    )

    assert '历史日报' in result['brain_judgment']['source_names']


def test_workshop_details_use_template_facts_not_rag_or_dingtalk_numbers() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            values={'cold_2050_daily': 80, 'cold_2050_month': 2422},
            extra={
                'rag': {'answer': '2050车间日产量999吨', 'citations': []},
                'dingtalk_messages': [{'text': '2050车间今天按777吨'}],
                'dingtalk_evidence': [{'recognized_text': '2050车间日产量888吨'}],
            },
        ),
    )

    text = result['text']
    assert '【2050车间】' in text
    assert '日产量：80吨，月累计：2422吨。' in text
    assert '999吨' not in text
    assert '888吨' not in text
    assert '777吨' not in text


def test_low_output_skill_match_rate_blocks_ready_template_and_lists_difference_fields() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            output_skill_alignment={
                'status': 'review_needed',
                'field_match_rate': 94.9,
                'matched_fields': 19,
                'expected_fields': 20,
                'difference_count': 2,
                'differences': [
                    {'field': 'total_output_daily', 'actual': 366, 'expected': 360},
                    {'field': 'cost_per_ton', 'actual': 1044, 'expected': 999},
                ],
                'char_match_rate': 95.2,
                'exact_match': False,
                'threshold': 95.0,
            },
        ),
    )

    assert result['status'] == 'blocked'
    assert result['formal_text'] == '6月21日，车间总产量日合计366吨。'
    assert BLOCKED_SENTENCE in result['text']
    assert '输出 skill 差异字段：total_output_daily、cost_per_ton' in result['text']
    assert '字段匹配率低于 95.0%' in result['text']
    assert '状态：需复核' in result['dingtalk_messages'][0]
    assert '状态：已对齐' not in result['dingtalk_messages'][0]


def test_missing_output_skill_alignment_does_not_fallback_to_audit_match_rate() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            audit_run={
                'status': 'completed',
                'match_rate': 1.0,
                'source_status': {'mes': 'ok', 'hub': 'ok', 'output_skill': 'missing'},
                'source_errors': {},
                'diffs': {},
                'suggested_actions': [],
            },
            output_skill_alignment={
                'status': 'missing',
                'file_name': None,
                'field_match_rate': None,
                'matched_fields': None,
                'expected_fields': None,
                'difference_count': None,
                'differences': [],
                'char_match_rate': None,
                'exact_match': False,
                'threshold': 95.0,
            },
        ),
    )

    assert result['status'] == 'blocked'
    assert BLOCKED_SENTENCE in result['text']
    assert '状态：已对齐' not in result['dingtalk_messages'][0]
    assert '状态：需复核' in result['dingtalk_messages'][0]


def test_threshold_can_be_custom_percent_and_still_allow_publish() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            output_skill_alignment={
                'status': 'passed',
                'field_match_rate': 92.0,
                'matched_fields': 18,
                'expected_fields': 20,
                'difference_count': 0,
                'differences': [],
                'char_match_rate': 97.0,
                'exact_match': False,
                'threshold': 90.0,
            },
        ),
    )

    assert result['status'] == 'ready'
    assert BLOCKED_SENTENCE not in result['text']
    assert '状态：已对齐' in result['dingtalk_messages'][0]


def test_threshold_accepts_ratio_value_for_release_gate() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(
            output_skill_alignment={
                'status': 'review_needed',
                'field_match_rate': 94.9,
                'matched_fields': 19,
                'expected_fields': 20,
                'difference_count': 0,
                'differences': [],
                'char_match_rate': 95.2,
                'exact_match': False,
                'threshold': 0.95,
            },
        ),
    )

    assert result['status'] == 'blocked'
    assert '字段匹配率低于 95.0%' in result['text']
